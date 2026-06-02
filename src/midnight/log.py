from ._storage import Store
import logging

class Log(Store):
    def __init__(self, identifier):
        super().__init__(identifier, suffix='.log')
        # Configure a dedicated logger that writes to this log file.
        # Use the file path as part of the logger name so multiple
        # Log instances don't clash.
        logger_name = f"midnight.log.{identifier}"
        self.logger = logging.getLogger(logger_name)
        # Avoid adding multiple handlers if logger already configured
        if not any(isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', '') == str(self.path) for h in self.logger.handlers):
            fh = logging.FileHandler(str(self.path), encoding='utf-8')
            fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
            self.logger.addHandler(fh)
            self.logger.setLevel(logging.INFO)
            self.logger.propagate = False

    def Tee(self, *args, level: str = 'info', sep: str = ' ', end: str = '\n', **kwargs):
        '''Print like `print()` and also log the same message to the file.

        Parameters:
        - *args: values to be printed/logged (joined by `sep`).
        - level: logging level to use (info, debug, warning, error, critical).
        - sep, end, flush: same semantics as `print()`.
        - **kwargs: additional keyword args forwarded to `print()`.
        '''
        # Format the message
        msg = sep.join(str(a) for a in args)

        # Log to file using configured logger
        if hasattr(self, 'logger') and self.logger is not None:
            level_name = (level or 'info').lower()
            log_method = getattr(self.logger, level_name, self.logger.info)
            try:
                log_method(msg)
            except Exception:
                # If logging fails for any reason, fall back to writing bytes
                try:
                    with open(self.path, 'a', encoding='utf-8') as f:
                        f.write(msg + (end or '\n'))
                except Exception:
                    pass