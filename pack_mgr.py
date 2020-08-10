import struct
import sys

fcodec = 'Shift_JIS'

def print_memory(memory):
    for j in range(int(len(memory)/16)):
        data = memory[j*16:(j+1)*16]
        lin = ['%02X' % i for i in data]
        print("%-40s%-40s"%(" ".join(lin),str(data)))
    if len(memory) % 16:
        j = int(len(memory) / 16)
        data = memory[j*16:]
        lin = ['%02X' % i for i in data]
        print("%-40s%-40s"%(" ".join(lin),str(data)))
    

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
                        return out_buf
                    opcode = in_buf[in_ptr] | 0xFF00    # 高两位置FF
                    in_ptr += 1
                if not opcode & 1:
                    break
                if in_ptr == in_size:
                    return out_buf
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

from PIL import Image
import numpy as np

class image_file:
    def __init__(self, filename, data):
        self.filename = filename
        self.data = None
        self.byte_num = 0
        (filetype, raw_size, _, self.resolution_x, self.resolution_y, img_type, _) = struct.unpack('II12sIII8s',data[0:0x28])
        if filetype != 0x40000:
            print("Warning : [" + filename + "] type [" + str(hex(filetype)) + "] is not a valid image file")
            return
        if img_type == 8:
            print("Warning : [" + filename + '] is not supported!')
        elif img_type == 0x18:
            self.byte_num = 3
        elif img_type == 0x20:
            self.byte_num = 4
        else:
            print("Warning : [" + filename + "] is not a valid image file")
            return
        reader = op_reader()
        self.data = reader.read(data[0x74:],raw_size)
    
    # ignore alpha channel
    # directory must be ended with / or \\
    # return 1 means success
    def save_to_dir(self, directory):
        if self.data == None:
            return 0
        img = [[None for x in range(self.resolution_x)] for y in range(self.resolution_y)]
        for y in range(self.resolution_y):
            for x in range(self.resolution_x):
                index = (y*self.resolution_x + x)*self.byte_num
                r = np.uint8(self.data[index])
                g = np.uint8(self.data[index+1])
                b = np.uint8(self.data[index+2])
                if self.byte_num == 4:
                    # alpha channel has been disabled
                    img[y][x] = [b,g,r]

                    # to enable alpha channel, just uncomment the following code
                    #a = np.uint8(self.data[index+3])
                    #img[y][x] = [b,g,r,a]
                else:
                    img[y][x] = [b,g,r]
        arr = np.array(img,dtype=np.uint8)
        c_img = Image.fromarray(arr)
        c_img.save(directory + self.filename + '.png')
        return 1
        

class pak_file_5_meta:
    meta_size = 0x68
    def __init__(self, data,f_type = None):
        self.data = data
        self.type = f_type
        (self.filename, self.offset, self.file_size, self.unknown) = struct.unpack('64sII32s',self.data)
        self.filename = self.filename.decode(fcodec).rstrip('\0')
    def set_type(self, f_type):
        if f_type == 0x40000:
            self.type = "IMG"
        else:
            self.type = None
    def print_info(self):
        print('%-32s%-20s%-16s%-20s'%(
            '[%s]'%self.filename,
            'size = %.2f KB'%(self.file_size/1024),
            'type = '+ str(self.type),
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
            self.fp.seek(self.header.raw_offset + file_meta.offset)
            file_meta.set_type(int.from_bytes(self.fp.read(4),byteorder='little'))
            self.file_metas.append(file_meta)
    def print_info(self):
        print("----------PAK FILE HEADER----------")
        self.header.print_info()
    def print_file_list(self):
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
        filename = "../../Graphic06.pak"
    else:
        filename = sys.argv[1]
    unpack_file = None
    if len(sys.argv) == 3:
        unpack_file = sys.argv[2]
    pak = pak_file(filename)
    pak.print_info()

    pak_name = os.path.basename(filename).split('.')[0]
    if not os.path.isdir(pak_name):
        os.mkdir(pak_name)
    for i in pak.file_metas:
        if unpack_file != None and i.filename != unpack_file:
            continue
        if i.type == "IMG": # image item
            offset = pak.header.raw_offset+i.offset
            pak.fp.seek(offset,0)
            img = image_file(i.filename,pak.fp.read(i.file_size))
            if img.save_to_dir(pak_name + '/'):
                print("[done]"+'\t',end='')
            else:
                print("[fail]"+'\t',end='')
        else:
            print("[skip]"+'\t',end='')
        i.print_info()
