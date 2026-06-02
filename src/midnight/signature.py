import platform
import numpy as np

class MachineSignature:
    '''
    Obtain cryptographic fingerprint
    of the running machine to use
    in the header of created map files.
    A small signature of authenticity.
    '''

    _MACHINE_ID = None

    @staticmethod
    def Fingerprint():
        if MachineSignature._MACHINE_ID is not None:
            return MachineSignature._MACHINE_ID
        import hashlib
        import uuid
        data = (
            platform.node() +
            platform.machine() +
            str(uuid.getnode())
        )
        
        fingerprint = hashlib.sha256(data.encode()).digest()
        
        parts = np.frombuffer(fingerprint, dtype='<u4')

        # Return a read-only uint32 view of the fingerprint bytes
        MachineSignature._MACHINE_ID = parts.copy()
        MachineSignature._MACHINE_ID.setflags(write=False)
        return MachineSignature._MACHINE_ID