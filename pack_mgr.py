import struct
import sys
from PIL import Image
import numpy as np

unpack_codec = 'Shift_JIS'
repack_codec = 'Shift_JIS'

def print_memory(memory):
    j = 0
    for j in range(int(len(memory)/16)):
        data = memory[j*16:(j+1)*16]
        lin = ['%02X' % i for i in data]
        print("0x%04x\t"%(j*16),end='')
        print("%-40s%-40s"%(" ".join(lin),str(data)))
    if len(memory) % 16:
        j = int(len(memory) / 16)
        data = memory[j*16:]
        lin = ['%02X' % i for i in data]
        print("0x%04x\t"%(j*16),end='')
        print("%-40s%-40s"%(" ".join(lin),str(data)))
    

class op_reader:
    def __init__(self):
        self.buf = bytearray([0 for _ in range(0x1000)])
        self.ptr = 0xFEE
    def unpack(self, in_buf):
        in_size = len(in_buf)
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
                if not opcode & 1:          # 最低位二进制为1时，直接拷贝
                    break                   # 最低为二进制为0时，从窗口拷贝
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
    def pack(self, in_buf):
        out_buf = bytearray()
        in_ptr = 0
        while in_ptr+8 < len(in_buf):
            out_buf.append(0xFF)      # 8 byte of copy，全部8byte都直接拷贝
            for _ in range(8):
                out_buf.append(in_buf[in_ptr])
                in_ptr += 1
        if in_ptr < len(in_buf):
            out_buf.append(0xFF)
            for _ in range(len(in_buf)-in_ptr):
                out_buf.append(in_buf[in_ptr])
                in_ptr += 1
        return out_buf

class pak_file_5_header:
    header_size = 0x48
    def __init__(self, data):
        self.data = data
        (self.magic, self.release, self.version, self.footer_size, self.flag, self.file_num, self.raw_offset, self.footer_offset) = struct.unpack('16s32sIIIIII',self.data)
        self.magic = self.magic.decode(unpack_codec).rstrip('\0')
        self.release = self.release.decode(unpack_codec)
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

class scw_file:
    type_code = 0x35776353
    type_name = "SCW"
    meta_size = 0x1C8
    def __init__(self, filename, data):
        self.filename = filename
        self.data = data
        self.header = data[0:self.meta_size]
        self.raw_data = None
                                                                        #
        (self.magic, self.major_v, self.flag, self.unpacked_size, self.raw_size, self.minor_v, self.show_num, self.text_num, self.unk_num, self.show_block_size, self.text_block_size, self.unk_block) = struct.unpack('16sIIIIIIIIII400s',data[0:self.meta_size])
        
        self.header = self.data[0:self.meta_size]
        reader = op_reader()
        self.unpacked_data = reader.unpack(self.xor(self.data[self.meta_size:]))
    def xor(self, data):
        out_buf = bytearray()
        for i in range(len(data)):
            byte_selected = np.uint8(data[i])
            byte_selected = byte_selected ^ np.uint8(i)
            out_buf.append(byte_selected)
        return out_buf
    def repack_to_data(self,directory):
        if not os.path.isfile(directory + self.filename + '.scw5'):
            print("No such file [" + self.filename + ']')
            return None
        if not os.path.isfile(directory + self.filename + '.txt'):  # only raw data, do not need repack
            with open(directory + self.filename + '.scw5','rb') as fp:
                return fp.read()
            return None
        byte_text = bytearray()
        byte_text_table = bytearray()
        text_num = 0
        with open(directory + self.filename + '.txt',encoding='utf-8') as fp:   # 从txt文件中读入文本，并处理
            text_ptr = 0
            text = []
            while True:
                c_line = fp.readline()
                if c_line == '' or c_line == '\n':
                    if len(text) == 1:  # 只有单行，应该是控制演出的
                        pass
                    elif len(text) == 2:    # 两行，意味着没有翻译
                        pass
                    elif len(text) == 3:    # 三行，意味着翻译了
                        del text[1] # 删除第二行，因为第二行是原文 
                    elif c_line == '':
                        break
                    tmp_bytes = "".join(text).rstrip('\n').encode(repack_codec) # 删除最后一个'\n'
                    byte_text += tmp_bytes
                    byte_text.append(0x00)  # 再在尾部添加一个'\0'
                    byte_text_table += int.to_bytes(text_ptr,length=4,byteorder='little',signed=False)
                    byte_text_table += int.to_bytes(len(tmp_bytes)+1,length=4,byteorder='little',signed=False)
                    text_ptr += len(tmp_bytes) + 1
                    text_num += 1
                    print(str(text_num) + "\t",end="")
                    print("".join(text).rstrip('\n'))
                    if c_line == '':
                        break
                    text = []   # clear text
                    continue
                text.append(c_line)
                # continue
        
        new_unpacked_data = bytearray()
        new_unpacked_data += self.unpacked_data[0:self.show_num*8]  # show table
        #print_memory(self.unpacked_data[0:self.show_num*8])
        offset = self.show_num * 8
        new_unpacked_data += byte_text_table    # text table
        #print('\n')
        #print_memory(byte_text_table)
        offset += self.text_num * 8
        #print(self.text_num)
        #print(text_num)
        new_unpacked_data += self.unpacked_data[offset:offset+self.unk_num*8]   # unk_table
        #print('\n')
        #print_memory(self.unpacked_data[offset:offset+self.unk_num*8])
        offset += self.unk_num * 8
        new_unpacked_data += self.unpacked_data[offset:offset+self.show_block_size]    # show data
        offset += self.show_block_size
        new_unpacked_data += byte_text
        if len(byte_text) < self.text_block_size:
            for _ in range(self.text_block_size - len(byte_text)):
                new_unpacked_data.append(0x00)
        elif len(byte_text) > self.text_block_size:
            print("Warning new text block is bigger than old one!")
        offset += self.text_block_size
        new_unpacked_data += self.unpacked_data[offset:]
        f = open(directory + self.filename + '.repacked','wb')
        f.write(new_unpacked_data)
        f.close()
        reader = op_reader()
        new_packed_data = reader.pack(self.xor(new_unpacked_data))
        self.raw_size = len(new_packed_data)

        new_header = struct.pack('16sIIIIIIIIII400s',self.magic, self.major_v, self.flag, len(new_unpacked_data), len(new_packed_data), self.minor_v, self.show_num, self.text_num, self.unk_num, self.show_block_size, len(byte_text), self.unk_block)
        return new_header + new_packed_data
        
        
    def unpack_to_dir(self,directory):
        if self.flag == 0xFFFFFFFF and self.major_v == 0x5000000 and self.magic.decode(unpack_codec).rstrip('\0') == 'Scw5.x' and self.minor_v == 0x1:
            reader = op_reader()
            unpacked_data = reader.unpack(self.xor(self.raw_data))

            if len(unpacked_data) != self.unpacked_size:
                print("Warning : [" + filename + '] unpacked size should be ' + str(hex(self.unpacked_size)) + " but " + str(hex(len(self.data)) + " unpacked!"))
                unpacked_data = None
                return False
        else:
            print("Warning : [" + filename + '] is not supported SCW file')
            return False
        f = open(directory + self.filename + '.scw5','wb')
        f.write(self.data)
        f.close()
        f = open(directory + self.filename + '.unpacked','wb')
        f.write(unpacked_data)
        f.close()
        if self.text_num and self.text_block_size:
            offset = self.show_num*8
            text_index_table = unpacked_data[offset:offset+self.text_num*8]
            offset += (self.text_num + self.unk_num) * 8 + self.show_block_size
            text_block_data = unpacked_data[offset:offset+self.text_block_size]
            text = []
            for i in range(self.text_num):
                (start, length) = struct.unpack('II',text_index_table[i*8:(i+1)*8])
                try:
                    text.append(text_block_data[start:start+length].decode(unpack_codec).replace('\0','\n\n'))
                except Exception:
                    text.append("[FAILED TO DECODE]\n")
                    text.append(str(text_block_data[start:start+length]) + "\n\n")
            txt_file = open(directory + self.filename + '.txt','w',encoding='utf-8')
            txt_file.writelines(text)
            txt_file.close()
        return True

class image_file:
    type_code = 0x40000
    type_name = "IMG"
    meta_size = 0x74
    def __init__(self, filename, data):
        self.filename = filename
        self.data = None
        self.byte_num = 0
        (filetype, raw_size, unpacked_size, _, _, self.resolution_x, self.resolution_y, img_type, self.use_alpha,_,_) = struct.unpack('IIIIIIIIII76s',data[0:self.meta_size])
        if filetype != self.type_code:
            print("Warning : [" + filename + "] type [" + str(hex(filetype)) + "] is not a valid image file")
            return
        if img_type == 8:
            self.byte_num = 1
        elif img_type == 0x18:
            self.byte_num = 3
        elif img_type == 0x20:
            self.byte_num = 4
        else:
            print("Warning : [" + filename + "] is not a valid image file")
            return
        reader = op_reader()
        self.data = reader.unpack(data[self.meta_size:])
        if len(self.data) != unpacked_size:
            print("Warning : [" + filename + '] unpacked size should be ' + str(hex(unpacked_size)) + " but " + str(hex(len(self.data)) + " unpacked!"))
            self.data = None
    
    # ignore alpha channel
    # directory must be ended with / or \\
    # return 1 means success
    def unpack_to_dir(self, directory):
        if self.data == None:
            return 0
        if self.byte_num == 1:
            print(str(self.resolution_x) + "x" + str(self.resolution_y))
            f = open(directory + self.filename,'wb')
            f.write(self.data)
            f.close()
            return 1
        img = [[None for x in range(self.resolution_x)] for y in range(self.resolution_y)]
        for y in range(self.resolution_y):
            for x in range(self.resolution_x):
                index = (y*self.resolution_x + x)*self.byte_num
                b = np.uint8(self.data[index])
                g = np.uint8(self.data[index+1])
                r = np.uint8(self.data[index+2])
                if self.byte_num == 4 and self.use_alpha == 0xf:
                    # use alpha channel
                    a = np.uint8(self.data[index+3])
                    img[y][x] = [r,g,b,a]
                elif self.byte_num == 4 or self.use_alpha != 0xf:
                    # skip alpha channel
                    img[y][x] = [r,g,b]
                else:
                    print("img file not supported")
                    return 0 
        arr = np.array(img,dtype=np.uint8)
        c_img = Image.fromarray(arr)
        c_img.save(directory + self.filename + '.png')
        return 1
        
# common file meta contained in DataPack5
class file_item:
    meta_size = 0x68
    def __init__(self, data,f_type = None):
        self.data = data
        self.type = f_type
        (self.filename, self.offset, self.file_size, self.unk32s) = struct.unpack('64sII32s',self.data)
        self.filename = self.filename.decode(unpack_codec).rstrip('\0')
    def set_type(self, f_type):
        if f_type == image_file.type_code:
            self.type = image_file.type_name
        elif f_type == scw_file.type_code:
            self.type = scw_file.type_name
        else:
            self.type = str(hex(f_type))
    def print_info(self):
        print('%-32s%-20s%-16s%-20s'%(
            '[%s]'%self.filename,
            #'size = %.2f KB'%(self.file_size/1024),
            'size = ' + hex(self.file_size),
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
        meta_buf = self.reader.unpack(self.fp.read(self.header.footer_size))
        self.file_items = []
        for i in range(self.header.file_num):
            item = file_item(meta_buf[i*file_item.meta_size:(i+1)*file_item.meta_size])
            self.fp.seek(self.header.raw_offset + item.offset)
            item.set_type(int.from_bytes(self.fp.read(4),byteorder='little'))
            self.file_items.append(item)
    def print_info(self):
        print("----------PAK FILE HEADER----------")
        self.header.print_info()
    def print_file_list(self):
        print("-----------------------------PAK FILE LIST ----------------------------")
        for i in self.file_items:
            i.print_info()
    def get_file_data(self, filename):
        fileitem = None
        if type(filename) == str:
            for i in self.file_items:
                if i.filename == filename:
                    fileitem = i
            if fileitem == None:
                print("File [%s] not found"%filename)
                return None
        elif type(filename) == file_item:
            if filename in self.file_items:
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

def unpack(pak_file_name, file_to_unpack = None, save_to_file:bool = True):
    pak = pak_file(pak_file_name)
    pak.print_info()

    pak_name = os.path.basename(pak_file_name).split('.')[0]
    if not os.path.isdir(pak_name):
        os.mkdir(pak_name)
    for i in pak.file_items:
        if file_to_unpack != None and i.filename != file_to_unpack:
            continue
        if i.type == "IMG": # image item
            img = image_file(i.filename,pak.get_file_data(i))
            if save_to_file:
                save_to_file_status = img.unpack_to_dir(pak_name + '/')
        elif i.type == "SCW":   # script item
            scw = scw_file(i.filename, pak.get_file_data(i))
            if save_to_file:
                save_to_file_status = scw.unpack_to_dir(pak_name + '/')
        else:
            if save_to_file:
                f = open(pak_name + '/' + i.filename,'wb')
                f.write(pak.get_file_data(i))
                f.close()
                save_to_file_status = True
        if not save_to_file:
            print("[skip]"+'\t',end='')
        else:
            if save_to_file_status:
                print("[done]"+'\t',end='')
            else:
                print("[fail]"+'\t',end='')
        i.print_info()

def pack_scw(directory):
    for filename in os.listdir(directory):
        if filename.split('.')[1] != 'scw5':
            continue
        filename = filename.split('.')[0]
        if filename != 'CEV001_102':
            continue
        scw = scw_file(filename, open(directory + filename + '.scw5','rb').read())
        print("WRITE " + filename + '.repacked')
        scw.repack_to_data(directory)
        


if __name__ == "__main__":
    pack_scw('SCR/')
    exit(0)
    save_to_file = True
    filename = '../../SCR.PAK'
    unpack_file = None

    if len(sys.argv) > 1:
        filename = sys.argv[1]
    if len(sys.argv) > 2:
        arg = sys.argv[2]
        if sys.argv[2].lower() == 'true':
            save_to_file = True
        elif sys.argv[2].lower() == 'false':
            save_to_file = False
        else:
            unpack_file = arg
    if len(sys.argv) > 3:
        if sys.argv[3].lower() == 'true':
            save_to_file = True
        elif sys.argv[3].lower() == 'false':
            save_to_file = False
    unpack(filename, unpack_file, save_to_file)
    
