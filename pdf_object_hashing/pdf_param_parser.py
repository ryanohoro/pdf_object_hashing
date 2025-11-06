#!/usr/bin/env python3
"""
windsurf helped with this code, testing it out. 
"""


class pdf_param_parser:
    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.length = len(data)
    
    def skip_whitespace(self):
        """Skip whitespace characters"""
        while self.pos < self.length and self.data[self.pos] in b' \t\n\r\f\0':
            self.pos += 1
    
    def get_current_char(self):
        """Get current character or None if at end"""
        if self.pos < self.length:
            return self.data[self.pos]
        return None
    
    def parse_name(self):
        """Parse a PDF name object (starts with /)"""
        if self.get_current_char() != ord(b'/'):
            return None
        
        self.pos += 1  # Skip the '/'
        start = self.pos
        
        while self.pos < self.length:
            c = self.data[self.pos]
            # End of name on delimiter
            if c in b' \t\n\r\f\0()<>[]{}/%':
                break
            # Handle #-escaped characters
            if c == ord(b'#'):
                if self.pos + 2 >= self.length:
                    break
                self.pos += 3  # Skip the # and two hex digits
                continue
            self.pos += 1
        
        return self.data[start:self.pos].decode('latin-1')
    
    def parse_value(self):
        """Parse a PDF value (dictionary, array, string, number, name, boolean, null)"""
        self.skip_whitespace()
        if self.pos >= self.length:
            return None
            
        c = self.get_current_char()
        
        # Dictionary
        if c == ord(b'<') and self.pos + 1 < self.length and self.data[self.pos + 1] == ord(b'<'):
            return self.parse_dictionary()
        # Array
        elif c == ord(b'['):
            return self.parse_array()
        # String (hex)
        elif c == ord(b'<'):
            return self.parse_hex_string()
        # String (literal)
        elif c == ord(b'('):
            return self.parse_literal_string()
        # Name
        elif c == ord(b'/'):
            return self.parse_name()
        # Number or boolean/null
        elif c in b'-+0123456789.':
            return self.parse_number_or_ref()
        # Boolean or null
        elif c in b'tfn':
            return self.parse_keyword()
        
        return None
    
    def parse_dictionary(self):
        """Parse a PDF dictionary"""
        if self.data[self.pos:self.pos+2] != b'<<':
            return None
        
        self.pos += 2
        result = {}
        
        while True:
            self.skip_whitespace()
            if self.pos >= self.length:
                break
                
            # Check for end of dictionary
            if self.data[self.pos:self.pos+2] == b'>>':
                self.pos += 2
                break
                
            # Parse key (must be a name)
            key = self.parse_name()
            if key is None:
                break
                
            # Parse value
            value = self.parse_value()
            if value is not None:
                result[key] = value
        
        return result
    
    def parse_array(self):
        """Parse a PDF array"""
        if self.get_current_char() != ord(b'['):
            return None
            
        self.pos += 1
        result = []
        
        while True:
            self.skip_whitespace()
            if self.pos >= self.length:
                break
                
            # Check for end of array
            if self.get_current_char() == ord(b']'):
                self.pos += 1
                break
                
            # Parse array element
            value = self.parse_value()
            if value is not None:
                result.append(value)
            else:
                break
                
        return result
    
    def parse_literal_string(self):
        """Parse a literal string (enclosed in parentheses)"""
        if self.get_current_char() != ord(b'('):
            return None
            
        self.pos += 1
        depth = 1
        start = self.pos
        result = []
        
        while self.pos < self.length:
            c = self.get_current_char()
            
            if c == ord(b'\\'):  # Escape sequence
                self.pos += 1
                if self.pos < self.length:
                    # Handle escape sequences (simplified)
                    esc = self.data[self.pos]
                    if esc in b'nrtbf()\\':
                        result.append(self.data[start:self.pos-1])
                        # Handle common escape sequences
                        if esc == ord(b'n'):
                            result.append(b'\n')
                        elif esc == ord(b'r'):
                            result.append(b'\r')
                        elif esc == ord(b't'):
                            result.append(b'\t')
                        elif esc == ord(b'b'):
                            result.append(b'\b')
                        elif esc == ord('f'):
                            result.append(b'\f')
                        else:
                            result.append(bytes([esc]))
                        start = self.pos + 1
                    # Handle octal escape sequences
                    elif ord(b'0') <= esc <= ord('7'):
                        # Parse up to 3 octal digits
                        val = 0
                        count = 0
                        while (count < 3 and 
                               self.pos < self.length and 
                               ord(b'0') <= self.data[self.pos] <= ord('7')):
                            val = (val << 3) + (self.data[self.pos] - ord(b'0'))
                            self.pos += 1
                            count += 1
                        result.append(self.data[start:self.pos-count-1])
                        result.append(bytes([val]))
                        start = self.pos
                        continue
                    self.pos += 1
            elif c == ord(b'('):
                depth += 1
                self.pos += 1
            elif c == ord(b')'):
                depth -= 1
                if depth == 0:
                    result.append(self.data[start:self.pos])
                    self.pos += 1
                    break
                self.pos += 1
            else:
                self.pos += 1
        
        return b''.join(result).decode('latin-1', errors='replace')
    
    def parse_hex_string(self):
        """Parse a hex string (enclosed in angle brackets)"""
        if self.get_current_char() != ord(b'<'):
            return None
            
        self.pos += 1
        start = self.pos
        hex_digits = b'0123456789ABCDEFabcdef'
        
        while (self.pos < self.length and 
               self.data[self.pos] != ord(b'>') and 
               self.data[self.pos] in hex_digits + b' \t\n\r\f\0'):
            self.pos += 1
            
        if self.pos >= self.length or self.data[self.pos] != ord(b'>'):
            return None
            
        hex_str = self.data[start:self.pos].translate(None, b' \t\n\r\f\0')
        self.pos += 1  # Skip the '>'
        
        # Convert hex string to bytes
        try:
            return bytes.fromhex(hex_str.decode('ascii')).decode('latin-1', errors='replace')
        except:
            return None
    
    def parse_number_or_ref(self):
        """Parse a number or object reference"""
        start = self.pos
        
        # Handle sign
        if self.get_current_char() in b'+-':
            self.pos += 1
            
        # Parse integer part
        while (self.pos < self.length and 
               ord(b'0') <= self.data[self.pos] <= ord('9')):
            self.pos += 1
            
        # Parse decimal part
        if (self.pos < self.length and 
            self.data[self.pos] == ord(b'.')):
            self.pos += 1
            while (self.pos < self.length and 
                   ord(b'0') <= self.data[self.pos] <= ord('9')):
                self.pos += 1
        
        # Check if this is an object reference (number number R)
        saved_pos = self.pos
        self.skip_whitespace()
        
        if (self.pos + 1 < self.length and 
            ord(b'0') <= self.data[self.pos] <= ord('9')):
            # Parse second number
            start2 = self.pos
            while (self.pos < self.length and 
                   ord(b'0') <= self.data[self.pos] <= ord('9')):
                self.pos += 1
                
            self.skip_whitespace()
            
            if (self.pos < self.length and 
                self.data[self.pos] == ord(b'R')):
                # It's a reference
                obj_num = int(self.data[start:start2])
                gen_num = int(self.data[start2:self.pos])
                self.pos += 1
                return {'type': 'reference', 'obj_num': obj_num, 'gen_num': gen_num}
        
        # Not a reference, just a number
        self.pos = saved_pos
        return float(self.data[start:self.pos].decode('ascii'))
    
    def parse_keyword(self):
        """Parse boolean or null keywords"""
        if self.data.startswith(b'true', self.pos):
            self.pos += 4
            return True
        elif self.data.startswith(b'false', self.pos):
            self.pos += 5
            return False
        elif self.data.startswith(b'null', self.pos):
            self.pos += 4
            return None
        return None

def find_dict_end(data, start_pos):
    """Find the matching '>>' for a '<<' at start_pos, handling nesting."""
    if not data.startswith(b'<<', start_pos):
        return -1
        
    depth = 1
    pos = start_pos + 2  # Skip the opening '<<'
    length = len(data)
    
    while pos < length - 1:  # Need at least 2 bytes left for '>>'
        if data.startswith(b'<<', pos):
            depth += 1
            pos += 2
        elif data.startswith(b'>>', pos):
            depth -= 1
            if depth == 0:
                return pos + 2  # Return position after the closing '>>'
            pos += 2
        else:
            pos += 1
            
    return -1  # No matching '>>' found

def parse_pdf_parameters(data):
    """Parse PDF parameters from binary data into a structured dictionary"""
    if not data:
        return {}
    
    # Look for dictionary pattern
    dict_start = data.find(b'<<')
    if dict_start >= 0:
        dict_end = find_dict_end(data, dict_start)
        if dict_end > dict_start:
            # Create a new parser with just the dictionary content
            parser = pdf_param_parser(b'<<' + data[dict_start+2:dict_end] + b'>>')
            return parser.parse_dictionary() or {}
    
    # If no dictionary found or error, try parsing as is
    parser = pdf_param_parser(data)
    return parser.parse_dictionary() or {}
