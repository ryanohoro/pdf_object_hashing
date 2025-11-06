# pdf-tools
PDF tools and libraries


Starting with a generic python library. I wanted this to help streamline creating rules and identifying what is weird about a PDF.  

## pdf_obj_hash.py
Command line tool to generate the PDF object hash of a given PDF.  Also supports scanning an entire directory.

### Usage

Run as a Python module (no installation required):
```bash
python -m pdf_object_hashing.pdf_obj_hash [-h] [-f FILE] [-d DIR] [--ftrace] [--debug] [--time-trace] [--print-hash-string] [--hunt-string HUNT_STRING] [--print-info]
```

### Options

``` 
Generate a PDF Object Hash of the provided file or files.

options:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  file to parse
  -d DIR, --dir DIR     directory to scan for PDFs
  --ftrace              DEBUG: prints functions as they're called
  --debug               DEBUG: prints mid-function debug info
  --time-trace          DEBUG: time the individual regex scans in the run.
  --print-hash-string   print the hash string instead of the obj hash
  --hunt-string HUNT_STRING
                        hunt for a complete or partial hash string ("Catalog|Producer|Pages|Page|None|Length")
  --print-info          kinda debug, print object and object number
```

### Examples

```bash
# Analyze a single PDF file
python -m pdf_object_hashing.pdf_obj_hash -f document.pdf

# Scan all PDFs in a directory
python -m pdf_object_hashing.pdf_obj_hash -d /path/to/pdfs/

# Print the hash string instead of MD5 hash
python -m pdf_object_hashing.pdf_obj_hash -f document.pdf --print-hash-string

# Hunt for specific object patterns
python -m pdf_object_hashing.pdf_obj_hash -f document.pdf --hunt-string "Catalog|Producer|Pages"
``` 

## What is a PDF Object Hash?
PDF Object Hash is a way to identifying similarities between PDFs without relying on the _content_ of the document. With object hashing we can identify the structure or skeleton of the document. Think of this as similar to an imphash or a ja3 hash. We extract out the object type and hash those to generate the hash. This allows us to quickly cluster similar documents and helps with identifying overlaps in disparate files. 

Recent updates to `pdf_obj_hash.py` and `pdf_lib.py` change how we parse objects, which should allow for better and more accurate parsing. This should (and in testing does) give us better results when dealing with "weird" pdfs (such as invalid xref entries). 

## pdf_lib.py
This is a python library for analyzing PDFs. 

Current features:
- parse xref table, xref streams, objects, stream objects, etc.
- extract stream content
- search object by object number, type, or some parameters 

Wish list:
- can we follow a chain of objects/ref objects? I don't remember if I added that or not.