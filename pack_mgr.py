import struct
import sys

fcodec = 'Shift_JIS'

def print_memory(memory):
    for j in range(int(len(memory)/16)):
        data = memory[j*16:(j+1)*16]
        lin = ['%02X' % i for i in data]
        print(" ".join(lin) + "\t" + str(data))
    if len(memory) % 16:
        j = int(len(memory) / 16)
        data = memory[(j+1)*16:]
        lin = ['%02X' % ord(i) for i in data]
        print(" ".join(lin) + "\t" + str(data))
        print(" ".join(lin))
    

class op_reader:
    def __init__(self):
        self.buf = bytearray([0 for _ in range(0x1000)])
        self.ptr = 0xFEE
    def read(self, in_buf, in_size):
        opcode = 0x0000
        out_buf = bytearray()
        self.buf = bytearray([0 for _ in range(0x1000)])
        in_ptr = 0
        self.ptr = 0xFEE
        while True:
            while True:
                opcode = opcode >> 1
                if not (opcode & 0x100):    # 获得下一个opcode
                    if in_ptr == in_size:
                        return 1
                    opcode = in_buf[in_ptr] | 0xFF00    # 高两位置FF
                    in_ptr += 1
                if not opcode & 1:
                    break
                if in_ptr == in_size:
                    return 1
                out_buf.append(in_buf[in_ptr])
                self.buf[self.ptr] = in_buf[in_ptr]
                in_ptr += 1
                self.ptr = (self.ptr + 1) & 0xFFF     # 内建窗口大小为0x0FFFF
            if in_ptr == in_size:
                break
            offset = in_buf[in_ptr]
            in_ptr += 1

            if in_ptr == in_size:
                break

            segment = (in_buf[in_ptr] & 0xF0) * 16  # 左移一个十六进制
            r_size = (in_buf[in_ptr] & 0x0F) + 2

            in_ptr += 1
            
            window_base = segment | offset
            index = 0
            
            while True:
                window_ptr = (window_base + index) & 0xFFF
                read_byte = self.buf[window_ptr]
                out_buf.append(read_byte)
                self.buf[self.ptr] = read_byte

                index += 1
                self.ptr = (self.ptr + 1) & 0xFFF
                
                if index > r_size:
                    break
        return out_buf

class pak_file_5_header:
    header_size = 0x48
    def __init__(self, data):
        self.data = data
        (self.magic, self.release, self.version, self.footer_size, self.flag, self.file_num, self.raw_offset, self.footer_offset) = struct.unpack('16s32sIIIIII',self.data)
        self.magic = self.magic.decode(fcodec).rstrip('\0')
        self.release = self.release.decode(fcodec)
        if self.magic != "DataPack5":
            print("Not a valid DataPack5 file")
    def print_info(self):
        print("       File Type : " + self.magic)
        print("         Release : " + self.release)
        print("         Version : " + str(hex(self.version)))
        print("        File Num : " + str(self.file_num))
        print("            Flag : " + str(bool(self.flag)))
        print("      Raw Offset : " + str(hex(self.raw_offset)))
        print("     Footer Size : " + str(hex(self.footer_size)))
        print("   Footer Offset : " + str(hex(self.footer_offset)))

class pak_file_5_meta:
    meta_size = 0x68
    def __init__(self, data):
        self.data = data
        (self.filename, self.offset, self.file_size, self.unknown) = struct.unpack('64sII32s',self.data)
        self.filename = self.filename.decode(fcodec).rstrip('\0')
    def print_info(self):
        print('%-32s%-20s%-20s'%(
            '[%s]'%self.filename,
            'size = %.2f KB'%(self.file_size/1024),
            'offset = 0x%08X'%self.offset
        ))

class pak_file_4_meta:
    meta_size = 0x48

class pak_file:
    def __init__(self, filename):
        self.filename = filename
        self.reader = op_reader()

        self.fp = open(self.filename,'rb')

        # read header
        self.header = pak_file_5_header(self.fp.read(pak_file_5_header.header_size))

        # read file metas(meta version 5)
        self.fp.seek(self.header.footer_offset,0)
        meta_buf = self.reader.read(self.fp.read(self.header.footer_size),self.header.footer_size)
        self.file_metas = []
        for i in range(self.header.file_num):
            file_meta = pak_file_5_meta(meta_buf[i*pak_file_5_meta.meta_size:(i+1)*pak_file_5_meta.meta_size])
            self.file_metas.append(file_meta)
    def print_info(self):
        print("----------PAK FILE HEADER----------")
        self.header.print_info()
        print()
        print("-----------------------------PAK FILE LIST ----------------------------")
        for i in self.file_metas:
            i.print_info()
    def get_file_data(self, filename):
        fileitem = None
        if type(filename) == str:
            for i in self.file_metas:
                if i.filename == filename:
                    fileitem = i
            if fileitem == None:
                print("File [%s] not found"%filename)
                return None
        elif type(filename) == pak_file_5_meta:
            if filename in self.file_metas:
                fileitem = filename
            else:
                print("File [%s] not found"%filename.filename)
                return None
        else:
            print("Unknown filename")
            return None
        self.fp.seek(fileitem.offset + self.header.raw_offset)
        return self.fp.read(fileitem.file_size)
    def __del__(self):
        self.fp.close()

import os

if __name__ == "__main__":
    if len(sys.argv) == 1:
        filename = "../Graphic06.pak"
    else:
        filename = sys.argv[1]
    f = pak_file(filename)

    pak_name = os.path.basename(filename).split('.')[0]
    if not os.path.isdir(pak_name):
        os.mkdir(pak_name)
    for i in f.file_metas:
        buf = f.get_file_data(i)
        
        if buf is not None:
            fp = open(pak_name+"/"+i.filename,'wb')
            fp.write(buf)
            fp.close()
            print("[√]"+'\t',end='')
            i.print_info()
        else:
            print("[X]"+'\t',end='')
            i.print_info()
