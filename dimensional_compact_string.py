from ctypes import CDLL, Structure, byref, c_int, c_void_p, c_char_p, c_int32, c_uint32, c_uint16, c_uint8, POINTER, c_int8, c_bool, c_char_p, c_size_t, cast
from enum import IntEnum
import platform, sys, time

# Types
class Encodings(Structure):
    _fields_ = [
        ("size", c_uint32),
        ("char_idx", c_uint16),
        ("chr", c_uint8),
        ("ext", c_uint8)
    ]

class Result(Structure):
    _fields_ = [
        ("result", c_int8),
        ("is_special", c_bool),
        ("output", c_void_p)
    ]

class WordEntry(Structure):
    _field_ = [
        ("word", c_char_p),
        ("len", c_size_t)
    ]

class WordList(Structure):
    _fields_ = [
        ("entries", POINTER(WordEntry)),
        ("count", c_size_t),
        ("capacity", c_size_t)
    ]

class Steps(Structure):
    _fiels_ = [
        ("ext", c_uint8)
    ]

class DimensionalMappingSteps(Structure):
    _fields_ = [
        ("bit_mapping_index", c_uint8),
        ("mapping_size", c_uint8),
        ("steps", POINTER(Steps)),
        ("step_count", c_uint32)
    ]

class ByteT(IntEnum):
    byte1               = 16
    byte2               = 8
    byte3               = 0

class u24(Structure):
    _fields_ = [
        ("byte1", c_uint8),
        ("byte2", c_uint8),
        ("byte3", c_uint8)
    ]

    def to_u32(self):
        """Python equivalent of create_u32_from_u24"""
        return (self.byte1 << 16) | (self.byte2 << 8) | self.byte3

    def get_byte(self, byte_pos):
        """Get specific byte: 0=byte1, 1=byte2, 2=byte3"""
        together = self.to_u32()

        # `byte_pos` has to be 16, 8 or 0, else return entire value
        if not byte_pos == ByteT.byte1 and not byte_pos == ByteT.byte2 and not byte_pos == ByteT.byte3:
            return together
        
        return (together >> byte_pos) & 0xFF

class OligosDimensionalMapping(Structure):
    _fields_ = [
        ("bits", c_uint8 * 8),
        ("bit_mappings", (POINTER(c_uint8) * 265) * 8),
        ("steps", POINTER(DimensionalMappingSteps) * 8),
        ("map_size", u24)
    ]

class DimensionalCompactString:
    def __init__(self):
        match platform.system():
            case 'Darwin': self.dcs = CDLL('dcs.dylib')
            case 'Windows': self.dcs = CDLL('dcs.dll')
            case 'Linux': self.dcs = CDLL('dcs.so')
            # fallback
            case _: self.dcs = CDLL('dcs.so')
        
        # Setup all functions used
        # Create/release encodings
        self.dcs.create_encodings.restype = POINTER(Encodings)
        self.dcs.release_encodings.argtypes = [POINTER(Encodings)]
        self.dcs.release_encodings.restype = None
        
        # Load word list
        self.dcs.WordList_load.argtypes = [POINTER(WordList), c_char_p]
        self.dcs.WordList_load.restype = c_bool

        # Append word list to dimensional mappings
        self.dcs.OD_ws_append.argtypes = [WordList, POINTER(Encodings)]
        self.dcs.OD_ws_append.restype = Result

        # Custom type (u24)
        self.dcs.uint24.argtypes = [c_size_t]
        self.dcs.uint24.restype = u24

        self.dcs.create_u32_from_u24.argtypes = [u24]
        self.dcs.create_u32_from_u24.restype = c_uint32

        self.dcs.create_u8_from_u24.argtypes = [u24, c_int]
        self.dcs.create_u8_from_u24.restype = c_uint32

        # Expose standard free()
        self.dcs.free.argtypes = [c_void_p]
        self.dcs.free.restype = None
    
    # Used for pointer return functions
    def _attempt(self, action, args: list = [], ret_raw=False):
        try: ptr = action() if args == [] else action(*args)
        except: sys.exit(1)

        if not ptr: sys.exit(1)
            
        return ptr.contents if not ret_raw else (ptr.contents, ptr)

    def init_encodings(self):
        self.encodings, self.encodings_ptr = self._attempt(
            self.dcs.create_encodings,
            ret_raw=True
        )
        print(f'Loaded {self.encodings.size} encodings')
    
    def release_encodings(self):
        print(f'Releasing {self.encodings.size} encodings')
        self.dcs.release_encodings(self.encodings)

    def load_wordlist(self, fpath="words.txt"):
        self.wordlist = WordList()

        if self.dcs.WordList_load(byref(self.wordlist), fpath.encode('utf-8')):
            print(f'Loaded {self.wordlist.count} words')
        else:
            sys.exit(1) # File not found
    
    def append_words(self):
        result = self.dcs.OD_ws_append(self.wordlist, self.encodings_ptr)

        if result.result == -1:
            sys.exit(1) # something went wrong
        
        self.odm_ptr = cast(result.output, POINTER(OligosDimensionalMapping))
        self.odm = self.odm_ptr.contents
        print(f"Map size: {self.odm.map_size.get_byte(ByteT.byte3)}")

# Code sectioned off into individual functions for better readability
def main():
    DCS = DimensionalCompactString()

    # Step 1: load encodings and the wordlist
    def load_encodings_and_wordlist():
        DCS.init_encodings()

        DCS.load_wordlist()
    load_encodings_and_wordlist()

    # Step 2: compress all the words into dimensional mapping
    #         (the map size should be a value that satisfies 0 >= value <= 255)
    def compress_wordlist():
        _start = time.time()
        DCS.append_words()
        _end = time.time()
        print(f'\n\tTime to compress {DCS.wordlist.count} words: {_end - _start}\n')
    compress_wordlist()

    # Cleanup
    def cleanup():
        DCS.dcs.free(DCS.odm_ptr)

        DCS.release_encodings()
    cleanup()

if __name__ == '__main__':
    start = time.time()
    main()
    end = time.time()
    print(f'\n\tTime for entire script: {end - start}\n')