#!/usr/bin/env python3
import re
import hashlib
import zlib
import time
from .pdf_param_parser import parse_pdf_parameters

"""

version 2 of the pdf lib
i think we have to parse xref entry, then xref stream, then stream objects and store them with the other objects

I would alos like it if we could be getting more grainular information from the PDFs we pass through...


still need to get the pdf obj hashing (and overall parsing to work)
I think it would make more sense to keep the std and stream objects separate in terms of parsing the object
data into the hash, but for searching for URIs and MediaBox values we def need to parse both.

Should we add to the seek functions so we can search the raw objects and the stream/decoded objects, or split that into separate functions?



I think we need a "follow" function.  You pass an object and if it's a ref object it will pull that object, and keep doing so until it finds the actual objects. 

we need a function to parse out any ref objects found in an object's parameters, so that it can be appended to the obj_dict/obj_data in that parse_params object. 

- we need to be able to pass in a stream object (not objstm) and decode it and look through the content for a <search term>
- we need to be able to properly parse objstm objects, and then parse out the objects within those objects. I thought we were doing that already but I guess not. 

"""


class pdf_object():
    def __init__(self, fname):
        self.fname = fname
        self.fdata = open(fname, 'rb').read()
        self.sha256 = hashlib.sha256(self.fdata).hexdigest()
        # data and objects 
        self.start_list = []
        self.revision_id_pairs = []
        self.object_offset_list = []
        self.xref_entries = {
            "std": [],
            "stream": [],
        }
        self.obj_dicts = []
        self.temp = None
        self.stream_objects = []
        self.cur_ws = None
        self.current_obj_number = None
        self.object_registry = {}
        self.current_objects = {}
        # regex patterns
        self.trailer_pattern = re.compile(b'trailer(?P<trailer_content>.*?)[\x00\x09\x0a\x0c\x0d\x20]{1,}%%EOF', re.MULTILINE+re.DOTALL)
        self.revision_id = re.compile(b'\/ID[\x00\x09\x0a\x0c\x0d\x20]*\[<(?P<current_id>[A-Za-z0-9]{32})><(?P<original_id>[A-Za-z0-9]{32})', re.MULTILINE)
        self.trailer_pattern2 = re.compile(b'(startxref.*?%%EOF)', re.MULTILINE+re.DOTALL)
        self.startxref_pattern = re.compile(b'startxref[\x00\x09\x0a\x0c\x0d\x20]{1,}([0-9]{1,})[\x00\x09\x0a\x0c\x0d\x20]{1,}')
        self.xref_pattern = re.compile(b'xref(?P<split_char>[\x00\x09\x0a\x0c\x0d\x20]{1,})(?P<xref_data>[0-9]{1,}.*?)trailer', re.MULTILINE+re.DOTALL)
        self.prev_xref = re.compile(b'/Prev[\x00\x09\x0a\x0c\x0d\x20]{1,}([0-9]{1,})', re.MULTILINE+re.DOTALL)
        self.stream_pattern2 = re.compile(b'(?P<obj_number>[0-9]{1,}) (?P<generation_id>[0-9]{1,}) obj[\x00\x09\x0a\x0c\x0d\x20]{1,}(?P<unk_data>.*?)(?P<stream_data>stream[\x0d\x0a].*?[\x0d\x0a]endstream)', re.MULTILINE+re.DOTALL)
        self.params_decode = re.compile(b'/DecodeParms[\x00\x09\x0a\x0c\x0d\x20]*?<<(?P<decode_params>.*?)>>', re.MULTILINE+re.DOTALL)
        self.params_w = re.compile(b'/W[\x00\x09\x0a\x0c\x0d\x20]*?\[(?P<w_array>.*?)\]')
        self.objstm_pattern = re.compile(b'(?P<obj_number>[0-9]{1,}) (?P<generation_id>[0-9]{1,}) obj[\x00\x09\x0a\x0c\x0d\x20]*?<<(?P<params>.*?)>>[\x00\x09\x0a\x0c\x0d\x20]*?stream([\x0d\x0a]*)(?P<stream>.*?)\3endstream', re.MULTILINE+re.DOTALL)
        self.n_extract = re.compile(b'/N[\x00\x09\x0a\x0c\x0d\x20]*?(?P<n_param>[0-9]{1,})', re.DOTALL)
        self.first_extract = re.compile(b'/First[\x00\x09\x0a\x0c\x0d\x20]*?(?P<first_param>[0-9]{1,})', re.DOTALL)
        self.object_pattern = re.compile(b'(?P<obj_number>[0-9]{1,}) (?P<generation_id>[0-9]{1,}) obj[\x00\x09\x0a\x0c\x0d\x20]{1,}(?P<full_obj_data>.*>>)[\x00\x09\x0a\x0c\x0d\x20]?(stream(?P<stream_data>.*?)endstream)?.*?endobj', re.MULTILINE+re.DOTALL)
        self.object_pattern_big = re.compile(b'(?P<obj_number>[0-9]{1,}) [0-9]{1,} obj(?P<ws>[\x00\x09\x0a\x0c\x0d\x20]{1,})(?P<unparsed>.*?)[\x00\x09\x0a\x0c\x0d\x20]{1,}endobj', re.MULTILINE+re.DOTALL)
        #self.obj_params_pattern = re.compile(b'\<\<(?P<params>.*)\>\>', re.MULTILINE+re.DOTALL)
        self.obj_params_pattern = re.compile(b'(?P<params><<.*>>)stream|(?P<params2><<.*>>)', re.MULTILINE+re.DOTALL)
        self.obj_stream_pattern = re.compile(b'stream([\x0d\x0a]*)(?P<stream>.*?)\1endstream', re.MULTILINE+re.DOTALL)
        self.params_key_location = re.compile(b'/(?P<key>[a-zA-Z0-9#]{1,})[\x00\x09\x0a\x0c\x0d\x20]*', re.MULTILINE+re.DOTALL)
        self.param_kv_pair = re.compile(b'/(?P<key>[a-zA-Z0-9#]{1,})[\x00\x09\x0a\x0c\x0d\x20]*(?P<value>.*?)/', re.MULTILINE+re.DOTALL)
        self.obj_type_pattern = re.compile(b'(?P<type>/Type[\x00\x0a\x0c\x0d\x20\x09]*/.*?)[\x00\x0a\x0c\x0d\x20\x09/>]', re.MULTILINE+re.DOTALL)
        self.obj_subtype_pattern = re.compile(b'(?P<type>/Subtype[\x00\x0a\x0c\x0d\x20\x09]*/.*?)[\x00\x0a\x0c\x0d\x20\x09/>]', re.MULTILINE+re.DOTALL)
        # debug
        self.func_trace = False
        self.debug = False
        self.timedbg = False
        self.start_time = time.time()


    def check_pdf_header(self):
        if self.func_trace:
            print(f"function: check_pdf_header")
        if not self.fdata[0:4] == b'%PDF':
            return False
        return True
    
    def check_trailer_content(self, trailer_data):
        if self.func_trace:
            print(f"function: check_trailer_content")
        if b'/ID' in trailer_data:
            rev_match = self.revision_id.search(trailer_data)
            if rev_match:
                current_id = rev_match.group('current_id')
                original_id = rev_match.group('original_id')
                self.revision_id_pairs.append([current_id, original_id])
    
    def run_regex_xref_scan(self):
        if self.func_trace:
            print(f"function: run_regex_scan")
        offset_list = []
        xref_regex = re.compile(b'[\x00\x09\x0a\x0c\x0d\x20]xref[\x00\x09\x0a\x0c\x0d\x20]{1,}.*?[\x00\x09\x0a\x0c\x0d\x20]{1,}trailer', re.MULTILINE+re.DOTALL)
        for match in xref_regex.finditer(self.fdata):
            if self.debug:
                print(f"--> xref match found: {match}")
            # need to add 1 here because the regex includes a whitespace character.
            offset_list.append(match.start() + 1)
        if self.timedbg:
            print(f"Timer: {time.time() - self.start_time}")
        xrefstream_regex = re.compile(b'[0-9]{1,} [0-9]{1,} obj[\x00\x09\x0a\x0c\x0d\x20]{1,}.*?\/XRef')
        for match in xrefstream_regex.finditer(self.fdata):
            if self.debug:
                print(f"--> xref stream match found: {match}")
            offset_list.append(match.start())
        if self.timedbg:
            print(f"Timer: {time.time() - self.start_time}")
        if offset_list:
            for entry in offset_list:
                self.start_list.append(entry)
        else:
            return False
    
    def trailer_params(self, trailer_match):
        if self.func_trace:
            print(f"function: trailer_params")
        offset_list = []
        if b'/Prev' in trailer_match:
            offset = int(trailer_match.split(b'/Prev ')[1].split(b'/')[0].split(b'>')[0])
            offset_list.append(offset)
        if b'/XRefStm' in trailer_match:
            offset = int(trailer_match.split(b'/XRefStm ')[1].split(b'/')[0].split(b'>')[0])
            offset_list.append(offset)
        return offset_list
    
    def uniq_list(self, in_list):
        if self.func_trace:
            print(f"function: uniq_list")
        out = []
        for i in in_list:
            if i not in out:
                out.append(i)
        return out
    
    def trailer_process(self):
        """
        trailer_process kicks off the whole chain of events required
        to grab the complete xref table contents (self.xref_entries) as well
        as the object_offset_list, which finds "IN_USE" objects and where they are located. 

        We know that some PDFs have incorrect offsets, so we might need some flexibility here...
        maybe it's a regex that runs against the whole file, im not sure.
        """
        if self.func_trace:
            print(f"function: trailer_process")
        trailer_matches = []
        if self.trailer_pattern.search(self.fdata):
            for trailer in self.trailer_pattern.finditer(self.fdata):
                trailer_matches.append(trailer)
                trailer_data = trailer.group('trailer_content')
                if trailer_data:
                    self.check_trailer_content(trailer_data)
        if self.trailer_pattern2.search(self.fdata):
            for trailer in self.trailer_pattern2.finditer(self.fdata):
                trailer_matches.append(trailer)
        if not trailer_matches:
            self.run_regex = True
            self.run_regex_xref_scan()
        for i in range(len(trailer_matches), 0, -1):
            offset_list = self.trailer_params(trailer_matches[i-1].group())
            start_xref_pos = None
            start_pos = self.startxref_pattern.search(trailer_matches[i-1].group())
            if start_pos:
                start_xref_pos = start_pos.groups()[0].decode()
            if start_xref_pos:
                if start_xref_pos not in self.start_list:
                    self.start_list.append(int(start_xref_pos))
            if offset_list:
                for offset in offset_list:
                    self.start_list.append(offset)
        self.start_list = self.uniq_list(self.start_list)
        if self.timedbg:
            print(f"Timer: {time.time() - self.start_time}")
        for item in self.start_list:
            if self.debug:
                print(f"--> start list item: {item}")
            self.prev_row = None
            try:
                self.parse_xref_table(item)
            except UnboundLocalError:
                print(f"(trailer_process) EXCEPTION: {self.fname} - {item}")
        if not self.object_offset_list:
            self.seek_obj_fallback()

    def parse_xref_table(self, start_pos):
        """
        with this we want to 1. parse the xref table (and xref stream)
        but also get the data from the parsed objects and store them in a dict, or list or whatever 
        so that we can call and reference them later on. 

        idk something like this? 

        self.xref_entries = {
            "stream" : [],
            "std" : [],
            }
        """
        if self.func_trace:
            print(f"function: parse_xref_table")
        xref_data = self.xref_pattern.match(self.fdata[start_pos:])
        if xref_data:
            split_char = xref_data.group('split_char').decode()
            xref_content = xref_data.group('xref_data').decode()
            xref_list = xref_content.split(split_char)
            cur_xref_table = []
            for i in xref_list:
                entry_list = [x for x in i.split(' ') if x]
                if len(entry_list) == 2:
                    start, count = entry_list
                    start = int(start)
                    count = int(count)
                elif len(entry_list) == 3:
                    object_offset, generation_id, free_in_use = entry_list
                    object_offset = int(object_offset)
                    generation_id = int(generation_id)
                    if len(free_in_use) > 1:
                        free_in_use = free_in_use[0:1]
                    if free_in_use == "n":
                        free_in_use = "in-use"
                    else:
                        free_in_use = "free"
                    start += 1
                    if free_in_use == "in-use" and (object_offset not in self.object_offset_list):
                        self.object_offset_list.append(object_offset)
                    cur_xref_table.append([object_offset, generation_id, free_in_use])
                    self.register_object_from_xref(start-1, generation_id, object_offset, free_in_use)
            if len(cur_xref_table) > 1:
                self.xref_entries["std"].append(cur_xref_table)
        else:
            obj_data = self.stream_pattern2.match(self.fdata[start_pos:])
            if obj_data:
                cur_xref_table = []
                if obj_data.group('unk_data'):
                    param_data = obj_data.group('unk_data')
                if obj_data.group('stream_data'):
                    stream_data = obj_data.group('stream_data')
                if b'/Type/XRef' in param_data.replace(b' ', b''):
                    if b'/Prev' in param_data:
                        value = int(param_data.split(b'/Prev ')[1].split(b'/')[0].decode())
                        if value not in self.start_list:
                            self.start_list.append(value)
                    params = self.params_extract(param_data)
                    if self.debug:
                        print(params)
                    if params:
                        self.decode_xref_stream(stream_data, params)
                        if self.temp:
                            self.xref_entries["stream"].append(self.temp)
                            self.temp = None
                else:
                    print(f"(parse_xref) Unexpected Data in xref stream regex - {self.fname}")
                    print(obj_data.group('unk_data'))
            else:
                self.run_regex_xref_scan()
    
    def seek_obj_fallback(self):
        """
        fallback method for finding objects when there is no xref entries. 
        """
        object_start_positions = []
        pos = -1
        obj_pattern = b' obj'
        while True:
            pos = self.fdata.find(obj_pattern, pos + 1)
            if pos == -1:
                break
            start = pos - 1
            while start >= 0 and self.fdata[start] in b'01234567890 ':
                start -= 1

            object_start_positions.append(start)
        if object_start_positions:
            self.object_offset_list = object_start_positions
    
    def params_extract(self, param_data):
        """
        this really only extracts params needed to decode the xref stream entry.
        should we add the rest of param extraction here, or is that overkill? 
        Would we eventually need or like this? 
        """
        if self.func_trace:
            print(f"function: params_extract")
        params = {}
        match_decode = self.params_decode.search(param_data)
        if match_decode:
            decode_params = match_decode.group('decode_params')
            if self.debug:
                print(decode_params)
            for kv in decode_params.split(b'/'):
                if kv not in {b'', b'\n'}:
                    try:
                        kv = [x for x in kv.split(b' ') if x]
                        if self.debug:
                            print(f"--> kv: {kv}")
                        if kv:
                            k, v = kv
                            params[k.decode()] = v.replace(b'\n', b'').decode()
                    except ValueError:
                        print("[!] exception: params_extract >> kv")
                        if self.debug:
                            print(kv)
                            print(type(kv))
                            print(f"file: {self.fname}")
        match_w = self.params_w.search(param_data)
        if match_w:
            w_array = match_w.group('w_array')
            w_values = w_array.decode().split(' ')
            w_values = [x for x in w_values if x]
            if len(w_values) != 3:
                w_values = None
            else:
                params["W"] = w_values
        if params:
            return params
  
    def decode_xref_stream(self, stream_bytes, param_dict):
        """
        decodes the xref stream object 
        """
        if self.func_trace:
            print(f"function: decode_xref_stream")
        w_array = param_dict["W"]
        predictor = int(param_dict.get("Predictor", 0))
        predictor_add = 0
        if predictor > 1:
            predictor_add = 1
        width = 0
        w = []
        if predictor_add:
            w.append(1)
        else:
            w.append(0)
        for i in w_array:
            width += int(i)
            w.append(int(i))
        data = stream_bytes.replace(b'stream\x0d\x0a', b'').replace(b'\x0d\x0aendstream',b'').replace(b'stream\x0a', b'').replace(b'\x0aendstream',b'').replace(b'stream\x0d', b'').replace(b'\x0dendstream',b'')
        try:
            decompressed = zlib.decompress(data)
        except zlib.error as z:
            if len(data) % (width + predictor_add) == 0:
                decompressed = data
            else:
                print(f"[-] zlib fail -- failed with file {self.fname}")
                if self.debug:
                    print(z)
                    fp = open('zlib_error.bin','wb')
                    fp.write(data)
                    fp.close()
                    exit()
        stream_list = []
        if len(decompressed) % (width + predictor_add) == 0:
            off = width + predictor_add
            for i in range(0, len(decompressed), off):
                row = decompressed[i:i+off]
                stream_list.append(self.clean_row(row, w))
        else:
            print(self.fname)
        if self.debug:
            print(f"--> decode_xref_stream: stream_list: {stream_list}")
        self.stream_list_parse(stream_list)

    def stream_list_parse(self, stream_list):
        """
        This adds to the object_offset_list (fills in the missing object offsets)
        stores the data in a temp storage and then we can use it in the calling 
        decode_xref_stream function. 

        looks like we're only handling some of the entry types. 
        """
        if self.func_trace:
            print("function: stream_list_parse")
        parsed_data = []
        for line in stream_list:
            entry_type = int.from_bytes(line[0], 'big')
            if isinstance(line[1], int):
                val2 = line[1]
            else:
                val2 = int.from_bytes(line[1], 'big')
            val3 = int.from_bytes(line[2], 'big')
            # Add after line 388 (after val3 = int.from_bytes(line[2], 'big')):
            obj_num = len(parsed_data)  # Current object number

            if entry_type == 1:  # Normal object
                # Existing code for object_offset_list
                self.register_object_from_xref(obj_num, val3, val2, "in-use")
                if val2 not in self.object_offset_list:
                    self.object_offset_list.append(val2)
            elif entry_type == 0:  # Free object  
                self.register_object_from_xref(obj_num, val3, 0, "free")
            elif entry_type == 2:  # Compressed object
                self.register_object_from_xref(obj_num, 0, val2, "compressed")
            parsed_data.append([entry_type, val2, val3])
        self.temp = parsed_data
        return True
    
    def predictor_process(self, row):
        """
        predictor process is only used as part of decoding xref stream objects
        """
        if self.func_trace:
            print('function: predictor_process')
        pred_value = row[0:1]
        data = row[1:]
        l = len(row)
        if self.prev_row == None:
            self.prev_row = b'\x00' * l
        if pred_value == b'\x02':
            new_row = [0, ] * (l - 1)
            for i in range(0, len(data)):
                try:
                    new_byte = (data[i] + self.prev_row[i]) % 256
                    new_row[i] = new_byte
                except Exception as e:
                    print(f"i: {i} \ndata: {data} \nprev_row: {self.prev_row}")
                    print(f"l:{l}\nl-1:{l-1}")
                    print(e)
                    print(type(e).__name__)
                    exit()
            self.prev_row = new_row
            b = bytes(new_row)
            return b
        else:
            print("[!] weird predictor value found in xref stream:")
            print(data)
            print(self.fname)
        
    def clean_row(self, row, w_array):
        """
        this is only used to clean up the w array values and do that "math"
        """ 
        if self.func_trace:
            print("function: clean_row")
        pred_size = w_array[0]
        entry_type_size = w_array[1]
        size2 = w_array[2]
        size3 = w_array[3]
        pred = row[0:pred_size]
        entry_val = row[pred_size:pred_size+entry_type_size]
        val2 = row[pred_size+entry_type_size:pred_size+entry_type_size+size2]
        val3 = row[pred_size+entry_type_size+size2:pred_size+entry_type_size+size2+size3]
        val2 = int.from_bytes(val2, 'big')
        if pred:
            new_bytes = self.predictor_process(row)
            if self.debug:
                print(f"--> clean_row: new bytes: {new_bytes}")
            new_entry = new_bytes[0:entry_type_size]
            new_val2 = new_bytes[entry_type_size:entry_type_size + size2]
            new_val3 = new_bytes[entry_type_size+size2:]
            return [new_entry, new_val2, new_val3]
        else:
            return [entry_val, val2, val3]
    
    # object stream parsing
    def start_object_parsing(self):
        """
        kicks off the process for getting the stream objects, so we can include 
        those in the parsed objects as well (searching for URIs with this, 
        finding ref objects, stuff like that

        Object Streaw parsing is not working correctly.  See the weird 0x1d adp 2025/60 PDF for example. 
        """
        if self.func_trace:
            print("function: start_object_parsing")
        obj_stms = self.seek_object_name(b'/ObjStm')
        if self.timedbg:
            print(f"Timer: {time.time() - self.start_time}")
        for obj in obj_stms:
            if self.debug:
                print(obj)
            match = self.objstm_pattern.search(obj)
            if match:
                if self.timedbg:
                    print(f"Timer: {time.time() - self.start_time}")
                if match.group('params'):
                    n_val, first_val = self.parse_stream_obj_params(match.group('params'))
                if match.group('stream') and n_val and first_val:
                    try:
                        if self.timedbg:
                            print(f"Timer: {time.time() - self.start_time}")
                        decode_data = zlib.decompress(match.group('stream'))
                    except zlib.error as e:
                        print(f'ZLIB ERROR {e}')
                        print(obj)
                        print(match.group('stream'))
                        exit()
                    if decode_data:
                        if self.timedbg:
                            print(f"Timer: {time.time() - self.start_time}")
                        decoded_stream = self.parse_decomp_obj(n_val, first_val, decode_data)
                        self.stream_objects.append(decoded_stream)
    
    def parse_decomp_obj(self, n, first, data):
        """
        returns the parsed data from the decompressed object stream data
        """
        if self.func_trace:
            print("function: parse_decomp_obj")
        output = []
        object_index = data[0:first]
        object_index_parsed = []
        object_data = data[first:]
        obj_list = object_index.split(b' ')
        for i in range(0, len(obj_list), 2):
            try:
                obj_number = int(obj_list[i].decode())
                start_pos = int(obj_list[i+1].decode())
                object_index_parsed.append([obj_number, start_pos])
            except IndexError:
                pass
            except ValueError:
                pass
        if n != len(object_index_parsed):
            return False
        for i in range(0, len(object_index_parsed)):
            pair = object_index_parsed[i]
            if i + 1 > n-1:
                next_pos = len(object_data)
            else:
                next_pair = object_index_parsed[i+1]
                next_obj, next_pos = next_pair
            obj, pos = pair
            data = {
                "object_number": obj, 
                "start": pos,
                "end": next_pos,
                "raw_data": object_data[pos:next_pos],
            }
            output.append(data)
        if self.timedbg:
            print(f"Timer: {time.time() - self.start_time}")
        return output

    def parse_stream_obj_params(self, param):
        """
        parses the parameters for the stream objects
        """
        if self.func_trace:
            print("function: parse_stream_obj_params")
        mn = self.n_extract.search(param)
        mf = self.first_extract.search(param)
        if mn:
            n_val = int(mn.group('n_param').decode())
        if mf:
            f_val = int(mf.group('first_param').decode())
        if self.timedbg:
            print(f"Timer: {time.time() - self.start_time}")
        if n_val and f_val:
            return n_val, f_val
    
    # searching functions
    def seek_object_number(self, number):
        """
        searches object_offset_list for an obj_number and returns that object
        expects a binary string: b'17' 

        
        What happens with searching for b'10' and when we see object 100?
        does that match when it should not?

        IT MIGHT be better to search some other structure instead of object_offset_list
        or at least note that we'll only get standard/raw objects and not anything compressed.

        we SHOULD be able to seek out an object from an OBJECT STREAM for things like URIs.
        """
        if self.func_trace:
            print("function: seek_object_number")
        for offset in self.object_offset_list:
            start = offset
            end = self.fdata.find(b'endobj', start+1)
            obj_data = self.fdata[start:end]
            num_data = obj_data[0:obj_data.find(b'obj')]
            obj_number = num_data.split(b' ')[0]
            if number == obj_number:
                if self.timedbg:
                    print(f"Timer: {time.time() - self.start_time}")
                return obj_data
    
    def seek_object_name(self, name):
        """
        returns object that matches the "name" pattern
        >> expects binary string, such as: b'Link' 
        -- we might want to actually return the whole object and from there
        -- take the time to parse out the rect/mediabox values and that way 
        -- we can loop back in on the object number associated with the mess. 
        -- if we want to find the URI this is probably what we NEED to do. 
        """
        if self.func_trace:
            print("function: seek_object_name")
        objects = []
        for offset in self.object_offset_list:
            start = offset
            end = self.fdata.find(b'endobj', start + 1)
            obj_data = self.fdata[start:end]
            if name in obj_data:
                objects.append(obj_data)
        if self.timedbg:
            print(f"Timer: {time.time() - self.start_time}")
        return objects

    def seek_obj_dict_by_number(self, number):
        """
        Trying a different process, looking over only the obj dict that we create
        
        it might be better to not do it this way, but I'll need to see if the param parsing happens
        separate from the other processing / object offset creation. 
        """
        for o in self.obj_dicts:
            if int(o["object_number"]) == number:
                 return o
    
    # searching the param dict for a specific key name? 
    def seek_param_key(self, key, d=None, current_path=None, results=None):
        """
        search the provided dict for a key and return that, looping
        over nested dicts if need be.  
        """
        if results is None:
            results = []
        if current_path is None:
            current_path = []
        
        if d is None:
            for obj in self.obj_dicts:
                if obj.get("object_params", ""):
                    obj_num = obj.get("object_number", "unknown").decode()
                    self.seek_param_key(key, obj["object_params"], current_path=[obj_num], results=results)
            return results

        for k, v in d.items():
            path = current_path + [k]
            if k == key:
                results.append((
                    current_path[0] if current_path else None, # object Number
                    ".".join(str(p) for p in path), # path to key
                    v, #value
                ))

            if isinstance(v, dict):
                self.seek_param_key(key, v, path, results)
            
        return results

    def seek_param_value(self, key, d=None, current_path=None, results=None):
        """
        search the provided dict for a value, and return that value, looping as needed.
        """
        if results is None:
            results = []
        if current_path is None:
            current_path = []

        if d is None:
            for obj in self.obj_dicts:
                if obj.get("object_params", ""):
                    obj_num = obj.get("object_number", "unknown").decode()
                    self.seek_param_value(key, obj["object_params"], current_path = [obj_num], results = results)
            return results
        
        for k, v in d.items():
            path = current_path + [k]
            if key in v:
                results.append((
                    current_path[0] if current_path else None,
                    ".".join(str(p) for p in path),
                    v,
                ))
            else:
                print(v)
            
            if isinstance(v, dict):
                self.seek_param_value(key, v, path, results)

        return results
    
    #std object parsing
    def pull_objects(self):
        """
        grabs each object from the offset list and 
        parses it
        """
        if self.func_trace:
            print("function: pull_objects")
        for item in self.object_offset_list:
            self.parse_pdf_object(item)

    # temp function
    def search_obj(self, start_pos):
        end = b'endobj'
        end_pos = self.fdata.find(end, start_pos)
        if b'/Type/Sig' in self.fdata[start_pos:end_pos+len(end)]:
            return False
        if self.timedbg:
            print(f"start Timer: {time.time() - self.start_time}")
        match = self.object_pattern_big.search(self.fdata[start_pos:end_pos+len(end)])
        if self.timedbg:
            print(f"end Timer: {time.time() - self.start_time}")
        if match:
            obj_number = match.group('obj_number')
            unparsed = match.group('unparsed')
            s = unparsed.find(b'endstream')
            if s:
                if b'<<' in unparsed[s:]:
                    print(f"{self.fname} --- found werid stream object at {obj_number}//{start_pos}")
    
    def parse_params(self, params):
        """
        parse the parameters of the object, we'll need some level of recurssion I think.

        let's start by looking for the TYPE which is the main thing we want here. 
            - /TYPE
            - /URI, /A, /S, /ANNOTS, /RECT, etc. 

        i think we want the output of the "type" query to be either "/Type/Pages" or "/Subtype/Image" that kind of thing. 
        I think knowing it's a type or a subtype is cool. 
        
        the spec mentions EOL (\x0a, \x0d and then two of them, maybe we use that? )

        when we iterate over the results, things with << at the end and >> at the end could be treated as if they are related... idk how but I think we can do that.  Or  is it even needed.  Does it matter that things are nested or is it really treated the same? 

        maybe we ignore it for now.

        we could maybe to a new regex just for extracting the type.  not sure if that would be better than the messy thing we have now or not. 
        """
        if self.func_trace:
            print("function: parse_params")
        data = parse_pdf_parameters(params)
        return data
      
    def parse_pdf_object(self, start_pos):
        """
        parses the object starting at start_pos

        Instead of directly copying the original version, i'm working
        on an update that should be a little simplier. 

        The idea is we parse out the object, and then from there, parse out the subsequent pieces:
        - object number
        - parameters
        - stream_data (if present)
        and then from parameters, we should be able to extract the TYPE (which is what we really need)

        Would it be better to have to the TYPE slam case, or do we keep case? 
        have we seen different case, i don't think so... that might be a spec standard that MUST be followed

        remember to implement the Type/Sig check to stop these slow downs on the regex. 

        """
        if self.func_trace:
            print("function: parse_pdf_object")
        end = b'endobj'
        end_pos = self.fdata.find(end, start_pos)
        obj_data = {
            'object_number': None,
            'object_type': None,
            'ref_objs': [],
            'object_params': None,
            'object_start': start_pos,
            'object_end': end_pos,
            'stream': False,

        }
        if b'/Type/Sig' in self.fdata[start_pos:end_pos+len(end)]:
            return False
        if b'stream' in self.fdata[start_pos:end_pos+len(end)] and b'endstream' in self.fdata[start_pos:end_pos+len(end)]:
            obj_data["stream"] = True
            # changes here
            stm_start = self.fdata[start_pos:end_pos+len(end)].find(b'stream')
            stm_end = self.fdata[start_pos:end_pos+len(end)].find(b'endstream')
            obj_data["stream_start_offset"] = stm_start + start_pos + 6
            obj_data["stream_end_offset"] = stm_end + start_pos
        match = self.object_pattern_big.search(self.fdata[start_pos:end_pos+len(end)])
        if match:
            if self.debug:
                print(f"--> parse_pdf_object // object_pattern_big regex|| {start_pos}")
            object_number = match.group('obj_number')
            # if object_number == None we need something to re-parse this. 
            obj_data["object_number"] = object_number
            self.cur_ws = match.group('ws')
            unparsed_data = match.group('unparsed')
            stream_match = self.obj_stream_pattern.search(unparsed_data)
            params_match = self.obj_params_pattern.search(unparsed_data)
            if params_match:
                if params_match.group('params'):
                    param_data = params_match.group('params')
                elif params_match.group('params2'):
                    param_data = params_match.group('params2')
                else:
                    print('hmmmm')
                    print(object_number)
                    print(params_match)
                param_dict = self.parse_params(param_data)
                if param_dict:
                    obj_data["object_params"] = param_dict
                    if param_dict.get("Subtype", "") and param_dict.get("Type", ""):
                        obj_data["object_type"] = param_dict["Type"] + "/" + param_dict["Subtype"]
                    elif param_dict.get("Type", ""):
                        obj_data["object_type"] = param_dict["Type"]
                    else:
                        obj_data["object_type"] = next(iter(param_dict))
        if obj_data["object_type"] == None:
            obj_data["object_type"] = "None"
        #print(obj_data["object_type"])
        self.obj_dicts.append(obj_data)

    # sorting objects

    def sort_obj_by_offset(self):
        return sorted(self.obj_dicts, key=lambda obj: obj['object_start'])

    def sort_obj_by_number(self):
        return sorted(self.obj_dicts, key=lambda obj: obj['object_number'])
    
    # testing this out

    def register_object_from_xref(self, obj_num, generation_id, object_offset, free_in_use):
        """
        Register an object from the xref table with proper revision handling.
        Uses generation numbers to track object versions - higher generation = newer version.
        """
        if self.func_trace:
            print(f"function: register_object_from_xref")
        if self.debug:
            print(f"Registering object {obj_num} gen {generation_id} status {free_in_use}")
        
        # Create object key using (object_number, generation)
        obj_key = (obj_num, generation_id)
        
        # Store in registry with full xref info
        self.object_registry[obj_key] = {
            'object_number': obj_num,
            'generation_id': generation_id,
            'object_offset': object_offset,
            'free_in_use': free_in_use,
            'file_position': object_offset
        }
        
        # Track current (active) version of each object number
        if free_in_use == "in-use":
            if obj_num not in self.current_objects:
                # First time seeing this object number
                self.current_objects[obj_num] = obj_key
            else:
                # Compare generations - higher generation wins
                current_key = self.current_objects[obj_num]
                current_gen = current_key[1]
                if generation_id > current_gen:
                    self.current_objects[obj_num] = obj_key
                    if self.debug:
                        print(f"Object {obj_num}: updated from gen {current_gen} to gen {generation_id}")
    
    def get_current_object_offsets(self):
        """
        Returns file offsets for only the current (active) version of each object.
        This eliminates duplicates by using xref generation numbers.
        """
        current_offsets = []
        for obj_num, obj_key in self.current_objects.items():
            if obj_key in self.object_registry:
                obj_info = self.object_registry[obj_key]
                if obj_info['free_in_use'] == "in-use":
                    current_offsets.append(obj_info['object_offset'])
        
        return sorted(current_offsets)  # Return in file order
    
    def get_revision_statistics(self):
        """
        Returns statistics about object revisions found in xref tables.
        """
        total_entries = len(self.object_registry)
        current_objects = len(self.current_objects)
        revised_objects = []
        
        # Find objects with multiple generations
        obj_generations = {}
        for (obj_num, gen_id), obj_info in self.object_registry.items():
            if obj_num not in obj_generations:
                obj_generations[obj_num] = []
            obj_generations[obj_num].append(gen_id)
        
        for obj_num, generations in obj_generations.items():
            if len(generations) > 1:
                revised_objects.append({
                    'object_number': obj_num,
                    'generations': sorted(generations),
                    'current_generation': max(generations)
                })
        
        return {
            'total_xref_entries': total_entries,
            'unique_objects': current_objects,
            'revised_objects': len(revised_objects),
            'revision_details': revised_objects
        }
    
    def pull_objects_xref_aware(self):
        """
        Parse objects using xref-aware approach that handles revisions properly.
        Only processes the current (highest generation) version of each object.
        """
        if self.func_trace:
            print("function: pull_objects_xref_aware")
        
        # Get offsets for current objects only
        current_offsets = self.get_current_object_offsets()
        
        if self.debug:
            print(f"Processing {len(current_offsets)} current objects (out of {len(self.object_registry)} total xref entries)")
        
        # Parse only current objects
        for offset in current_offsets:
            self.parse_pdf_object(offset)

    def search_all_object_streams_for_object(self, target_obj_num):
        """
        Search all object streams for a specific object number
        """
        results = []
        
        # Get all ObjStm objects
        objstm_objects = []
        for obj in self.obj_dicts:
            if obj.get("object_type") == "ObjStm" or (
                obj.get("object_params") and 
                obj["object_params"].get("Type") == "ObjStm"
            ):
                objstm_objects.append(obj)
        
        # Search each object stream
        for objstm in objstm_objects:
            # Parse the object stream if not already done
            if "stream_data" in objstm:
                # Extract N and First parameters
                params = objstm.get("object_params", {})
                n_val = params.get("N")
                first_val = params.get("First")
                
                if n_val and first_val:
                    # Parse the object index
                    stream_data = objstm["stream_data"]
                    try:
                        decompressed = zlib.decompress(stream_data)
                        index_data = decompressed[:first_val]
                        
                        # Parse object numbers from index
                        tokens = index_data.split()
                        for i in range(0, len(tokens), 2):
                            try:
                                obj_num = int(tokens[i])
                                if obj_num == target_obj_num:
                                    offset = int(tokens[i+1])
                                    results.append({
                                        'found_in_objstm': objstm['object_number'],
                                        'object_number': obj_num,
                                        'offset_in_stream': offset
                                    })
                            except (ValueError, IndexError):
                                continue
                                
                    except zlib.error:
                        continue
        
        return results

    def get_objects_by_file_order(self, in_use_only=False):
        """
        return the objects in the order they appear in the file
        instead of the object order (which is how we're doing it currently)

        current-only flag is optional to see if we want only the "in-use" files. 
        """
        if in_use_only:
            current_offsets = self.get_current_object_offsets()
            file_ordered_objects = []
            for offset in current_offsets:
                for obj in self.obj_dicts:
                    if obj.get('object_start') == offset:
                        file_ordered_objects.append(obj)
                        break
            return file_ordered_objects
        else:
            valid_objects = [obj for obj in self.obj_dicts if obj.get('object_start') is not None]
            return sorted(valid_objects, key=lambda obj: obj['object_start'])