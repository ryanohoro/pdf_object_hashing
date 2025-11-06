#!/usr/bin/env python3

from .pdf_lib import pdf_object as po
import argparse
import glob
import os
import time
import hashlib

class pdf_tester():
    def __init__(self):
        self.args = pdf_tester.parse_arguments()
        self.pdf_object = None

    def generate_file_list(self):
        file_list = []
        if self.args.dir and self.args.file:
            print("[-] ERROR: Cannot set both --dir and --file")
        if self.args.file:
            return [self.args.file]
        if self.args.dir:
            if self.args.dir == ".":
                flist = glob.glob('*')
            elif self.args.dir[-1] != "/":
                flist = glob.glob(self.args.dir + "/*")
            else:
                flist = glob.glob(self.args.dir + "*")
            if flist:
                for f in flist:
                    if os.path.isfile(f):
                        self.pdf_object = po(f)
                        if self.pdf_object.check_pdf_header():
                            file_list.append(f)
        return file_list

    @staticmethod
    def parse_arguments():
        argparser = argparse.ArgumentParser(description="Generate a PDF Object Hash of the provided file or files.")
        argparser.add_argument("-f", "--file", help = "file to parse")
        argparser.add_argument("-d", "--dir", help = "directory to scan for PDFs")
        argparser.add_argument("--ftrace", help="DEBUG: prints functions as they're called", dest="ftrace", action="store_true")
        argparser.add_argument("--debug", help="DEBUG: prints mid-function debug info", dest="debug", action="store_true")
        argparser.add_argument("--time-trace", help="DEBUG: time the individual regex scans in the run.", dest="timedebug", action="store_true")
        argparser.add_argument("--print-hash-string", help="print the hash string instead of the obj hash", dest="print_hash_string", action="store_true")
        argparser.add_argument("--hunt-string", help="hunt for a complete or partial hash string (\"Catalog|Producer|Pages|Page|None|Length\")", type=str, dest="hunt_string", action="store")
        argparser.add_argument("--print-info", dest='info', help="kinda debug, print object and object number", action="store_true")
        args = argparser.parse_args()
        return args
    


def main():
    """Main entry point for the pdf-obj-hash command line tool."""
    pdf = pdf_tester()
    file_list = pdf.generate_file_list()
    for f in file_list:
        start = time.time()
        #print(f"------ Parsing {f} ------")
        pdf.pdf_object = po(f)
        if pdf.args.ftrace:
            pdf.pdf_object.func_trace = True
        if pdf.args.debug:
            pdf.pdf_object.debug = True
        if pdf.args.timedebug:
            pdf.pdf_object.timedbg = True
        # starting the pdf lib process:
        pdf.pdf_object.check_pdf_header()
        pdf.pdf_object.trailer_process()
        pdf.pdf_object.start_object_parsing()
        pdf.pdf_object.pull_objects_xref_aware()
        runtime = time.time() - start
        obj_hash_str = ""
        file_ordered_objects = pdf.pdf_object.get_objects_by_file_order(in_use_only=True)
        for item in file_ordered_objects:
        #for item in pdf.pdf_object.obj_dicts:
            obj_hash_str += item["object_type"] + "|"
            if pdf.args.info:
                print(item)
                #print(f"{item['object_number']} - {item['object_type']}")
        if pdf.args.hunt_string:
            if pdf.args.hunt_string == obj_hash_str:
                print(f"[100% match]:{pdf.pdf_object.sha256},{obj_hash_str}")
            elif pdf.args.hunt_string in obj_hash_str:
                print(f"[partial match]:{pdf.pdf_object.sha256},{obj_hash_str}")
        elif pdf.args.print_hash_string:
            print(f"{pdf.pdf_object.sha256},{obj_hash_str},{runtime}")
        else:
            obj_hash = hashlib.md5(obj_hash_str.encode()).hexdigest()
            print(f"{pdf.pdf_object.sha256},{obj_hash},{runtime}")
        if pdf.args.debug:
            print(f"Object Count: {len(pdf.pdf_object.object_offset_list)} // runtime: {runtime}")
            print(f"xref entries: {pdf.pdf_object.xref_entries}")


if __name__ == "__main__":
    main()
