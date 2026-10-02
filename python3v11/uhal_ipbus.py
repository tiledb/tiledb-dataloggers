"""Raw-address IPbus client on top of the uHAL Python library.

Drop-in replacement for Herakles.Uhal. A single-word Read returns an int.
A block Read returns a list of ints. Write accepts an int or a list/tuple.
FIFO (non-incrementing) accesses use uHAL NON_INCREMENTAL block mode.

Herakles connection strings of the form
``tcp://<controlhub>:10203?target=<ppr>:50001`` are rewritten to the uHAL
control-hub URI ``chtcp-2.0://...``. URIs that already name a uHAL protocol
(``chtcp-2.0``, ``ipbusudp-2.0``, ``ipbustcp-2.0``, ...) are passed through.

A bus timeout is treated as an unimplemented slave: Read returns
0xFFFFFFFF and does not raise, matching Herakles and the tested
tile_scripts eye-readback handling. uHAL ERROR logs for those timeouts
are suppressed so missing GTH/FEB addresses do not flood the logger.
"""

import uhal

uhal.setLogLevelTo(uhal.LogLevel.ERROR)

_BUS_TIMEOUT = "bus timeout"
_MISSING = 0xFFFFFFFF


def to_uhal_uri(uri):
    """Translate a Herakles control-hub URI into a uHAL URI."""
    if uri.startswith("tcp://"):
        return "chtcp-2.0://" + uri[len("tcp://"):]
    return uri


def _mask32(value):
    return int(value) & 0xFFFFFFFF


def _is_bus_timeout(exc):
    return _BUS_TIMEOUT in str(exc).lower()


class Uhal:
    """uHAL client with the Herakles Read / Write / ReadFIFO / SetVerbose API."""

    def __init__(self, uri, device_id="ppr"):
        self.uri = to_uhal_uri(uri)
        self._client = uhal.buildClient(device_id, self.uri)
        self._log_level = uhal.LogLevel.ERROR

    def SetVerbose(self, enable):
        self._log_level = uhal.LogLevel.DEBUG if enable else uhal.LogLevel.ERROR
        uhal.setLogLevelTo(self._log_level)

    def Sync(self):
        """Present for Herakles callers. uHAL resynchronises packet IDs itself."""
        return None

    def _read_once(self, address, size, fifo):
        if size == 1 and not fifo:
            val = self._client.read(address)
            self._client.dispatch()
            return int(val) & 0xFFFFFFFF
        mode = (
            uhal.BlockReadWriteMode.NON_INCREMENTAL
            if fifo
            else uhal.BlockReadWriteMode.INCREMENTAL
        )
        val = self._client.readBlock(address, size, mode)
        self._client.dispatch()
        if size == 1:
            words = val.value()
            return int(words[0]) & 0xFFFFFFFF
        return [int(word) & 0xFFFFFFFF for word in val.value()]

    def Read(self, address, size=1, fifo=False):
        address = _mask32(address)
        size = int(size)
        if size < 1:
            raise ValueError("Read size must be >= 1")
        uhal.setLogLevelTo(uhal.LogLevel.FATAL)
        try:
            return self._read_once(address, size, fifo)
        except uhal.exception as exc:
            if not _is_bus_timeout(exc):
                raise
            if size == 1:
                return _MISSING
            return [_MISSING] * size
        finally:
            uhal.setLogLevelTo(self._log_level)

    def ReadFIFO(self, address, size, fifo=True):
        return self.Read(address, size, fifo=bool(fifo))

    def Write(self, address, values, fifo=False):
        address = _mask32(address)
        if isinstance(values, (list, tuple)):
            words = [_mask32(word) for word in values]
            if not words:
                raise ValueError("Write list is empty")
            if len(words) == 1 and not fifo:
                self._client.write(address, words[0])
            else:
                mode = (
                    uhal.BlockReadWriteMode.NON_INCREMENTAL
                    if fifo
                    else uhal.BlockReadWriteMode.INCREMENTAL
                )
                self._client.writeBlock(address, words, mode)
        else:
            self._client.write(address, _mask32(values))
        self._client.dispatch()
        return None
