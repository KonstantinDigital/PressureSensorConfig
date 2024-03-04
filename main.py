#!/usr/bin/env python3
# coding: utf-8
# 2023 KDigital
# Программа для конфигурирования датчика давления ООО"Датчики и системы" 415М-ДИ

import socket
import modbus_tk.exceptions
import serial
from serial.tools import list_ports
import serial.serialutil
import modbus_tk.defines as mb_def
import modbus_tk.modbus_rtu as mb_rtu
import modbus_tk.modbus_tcp as mb_tcp
import keyboard
from threading import Thread
import re

sock = None
port_obj = None
port_search = False


class _RangeError(Exception):
    pass


class Sock(socket.socket):
    """
    Класс для объекта TCP порта
    """
    def __init__(self, host, port, test=False):
        super(Sock, self).__init__(socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.port = port
        self.test = test
        self.settimeout(0.25)
        self.is_connect = False
        self.try_connect()

    def try_connect(self):
        if self.test:
            self.settimeout(0.001)
            try:
                if self.connect_ex((self.host, self.port)):
                    self.is_connect = False
                else:
                    print()
                    border_print("Подключено к " + self.host + ":" + str(self.port), "#")
                    self.is_connect = True
            except socket.gaierror:
                self.is_connect = False
        else:
            try:
                if self.connect_ex((self.host, self.port)):
                    border_print("Подключиться к " + self.host + ":" + str(self.port) + " не удалось", "!")
                    self.is_connect = False
                else:
                    border_print("Подключено к " + self.host + ":" + str(self.port), "#")
                    self.is_connect = True
            except socket.gaierror:
                border_print("Подключиться к " + self.host + ":" + str(self.port) + " не удалось", "!")
                self.is_connect = False

    def check_connect(self):
        return self.is_connect


class Port(serial.Serial):
    """
    Класс для объекта COM порта
    """
    def __init__(self, port=None):
        super(Port, self).__init__()
        self.parity = serial.PARITY_NONE
        self.stopbits = 1
        self.bytesize = 8
        self.timeout = 0.1
        if port is not None:
            self.port = "COM{}".format(port)
        self.try_connect()

    def try_connect(self):
        if self.port is None:
            ports = list_ports.comports()
            sort_ports = []
            for com_port in ports:
                if ("ch340" in com_port.description.lower()) or ("serial" in com_port.description.lower()):
                    sort_ports.append(com_port)

            for com_port in ports:
                if com_port not in sort_ports:
                    sort_ports.append(com_port)

            for com_port in sort_ports:
                self.port = com_port.device
                try:
                    self.open()
                    if self.check_ports():
                        border_print("Подключено к " + self.port, "#")
                        break
                    else:
                        self.port = None
                except serial.serialutil.SerialException:
                    self.port = None
        else:
            try:
                self.open()
                if self.check_ports():
                    border_print("Подключено к " + self.port, "#")
                else:
                    border_print("Подключиться к " + self.port + " не удалось", "!")
                    self.port = None
            except serial.serialutil.SerialException:
                border_print("Подключиться к " + self.port + " не удалось", "!")
                self.port = None

    def check_ports(self):
        return self.is_open


class Device(mb_rtu.RtuMaster):
    """
    Экземпляр устройства в сети по протоколу ModbusRTU
    """
    def __init__(self, port, slave=None):
        super(Device, self).__init__(serial=port)
        self.slave = slave
        self.is_connect = False
        self.set_timeout(0.1)
        self.stop_search = False
        self.thread1 = Thread(target=self.wait_exit, daemon=True)
        self.thread1.start()
        self.try_connect()

    def wait_exit(self):
        try:
            keyboard.wait("esc")
            self.stop_search = True
        except KeyError:
            self.stop_search = True

    def try_connect(self):
        if self.slave is None:
            print("\nНажмите [ Esc ] чтобы прервать процесс поиска")
            devices = range(1, 248)
            for device in devices:
                if self.stop_search:
                    break
                if self.check_connect():
                    break
                self.slave = device
                print("\nПытаемся подключиться к датчику по адресу", self.slave, end="")
                err_cnt = 0
                while err_cnt < 10:
                    print(" .", end="", flush=True)
                    try:
                        get_data = self.execute(self.slave, mb_def.READ_HOLDING_REGISTERS, 249, 1)
                        if get_data[0] == self.slave:
                            self.is_connect = True
                            print()
                            border_print("Подключились к датчику по адресу " + str(self.slave), "#")
                            break
                    except modbus_tk.exceptions.ModbusInvalidResponseError:
                        self.is_connect = False
                    err_cnt += 1
        else:
            print("\nПытаемся подключиться к датчику по адресу", self.slave, end="")
            err_cnt = 0
            while err_cnt < 10:
                print(" .", end="", flush=True)
                try:
                    get_data = self.execute(self.slave, mb_def.READ_HOLDING_REGISTERS, 249, 1)
                    if get_data[0] == self.slave:
                        self.is_connect = True
                        print()
                        border_print("Подключились к датчику по адресу " + str(self.slave), "#")
                        break
                except modbus_tk.exceptions.ModbusInvalidResponseError:
                    self.is_connect = False
                err_cnt += 1
        if not self.is_connect:
            print()
            border_print("Подключиться не удалось", "!")

    def check_connect(self):
        return self.is_connect

    def write_slave(self, new_address):
        old_address = self.slave

        if new_address is not None and new_address > 0 and new_address != old_address:
            print("\nПишем новый адрес " + str(new_address) + " в устройство", end="")
            try_cnt = 0
            while try_cnt < 10:
                print(" .", end="", flush=True)
                try:
                    self.execute(self.slave, mb_def.WRITE_SINGLE_REGISTER, 249, 1, new_address)
                except modbus_tk.exceptions.ModbusInvalidResponseError:
                    try_cnt += 1
            print()
            self.slave = new_address
            if not self.try_new_slave():
                self.slave = old_address
        else:
            border_print("Адрес датчика не изменен", "#")

    def try_new_slave(self):
        err_cnt = 0
        while err_cnt < 10:
            try:
                get_data = self.execute(self.slave, mb_def.READ_HOLDING_REGISTERS, 249, 1)
                if get_data[0] == self.slave:
                    self.is_connect = True
                    border_print("Новый адрес датчика записан", "#")
                    break
                # print(get_data[0])
            except modbus_tk.exceptions.ModbusInvalidResponseError:
                self.is_connect = False
            err_cnt += 1
        if not self.is_connect:
            border_print("Запись не удалась", "!")
            return False
        return True


class TcpDevice(mb_tcp.TcpMaster):
    """
    Экземпляр устройства в сети по протоколу ModbusTCP
    """
    def __init__(self, host, port, slave=None):
        super(TcpDevice, self).__init__(host=host, port=port, timeout_in_sec=0.25)
        self.slave = slave
        self.is_connect = False
        # self.set_timeout(0.25)
        self.stop_search = False
        self.thread1 = Thread(target=self.wait_exit, daemon=True)
        self.thread1.start()
        self.try_connect()

    def wait_exit(self):
        try:
            keyboard.wait("esc")
            self.stop_search = True
        except KeyError:
            self.stop_search = True

    def try_connect(self):
        if self.slave is None:
            print("\nНажмите [ Esc ] чтобы прервать процесс поиска")
            devices = range(1, 248)
            for device in devices:
                if self.stop_search:
                    break
                if self.check_connect():
                    break
                self.slave = device
                print("\nПытаемся подключиться к датчику по адресу", self.slave, end="")
                err_cnt = 0
                while err_cnt < 10:
                    print(" .", end="", flush=True)
                    try:
                        get_data = self.execute(self.slave, mb_def.READ_HOLDING_REGISTERS, 249, 1)
                        if get_data[0] == self.slave:
                            self.is_connect = True
                            print()
                            border_print("Подключились к датчику по адресу " + str(self.slave), "#")
                            break
                    except (socket.timeout, modbus_tk.modbus_tcp.ModbusInvalidMbapError):
                        self.is_connect = False
                    err_cnt += 1
        else:
            print("\nПытаемся подключиться к датчику по адресу", self.slave, end="")
            err_cnt = 0
            while err_cnt < 10:
                print(" .", end="", flush=True)
                try:
                    get_data = self.execute(self.slave, mb_def.READ_HOLDING_REGISTERS, 249, 1)
                    if get_data[0] == self.slave:
                        self.is_connect = True
                        print()
                        border_print("Подключились к датчику по адресу " + str(self.slave), "#")
                        break
                except (socket.timeout, modbus_tk.modbus_tcp.ModbusInvalidMbapError):
                    self.is_connect = False
                err_cnt += 1
        if not self.is_connect:
            print()
            border_print("Подключиться не удалось", "!")

    def check_connect(self):
        return self.is_connect

    def write_slave(self, new_address):
        old_address = self.slave

        if new_address is not None and new_address > 0 and new_address != old_address:
            print("\nПишем новый адрес " + str(new_address) + " в устройство", end="")
            try_cnt = 0
            while try_cnt < 10:
                print(" .", end="", flush=True)
                try:
                    self.execute(self.slave, mb_def.WRITE_SINGLE_REGISTER, 249, 1, new_address)
                except (socket.timeout, modbus_tk.modbus_tcp.ModbusInvalidMbapError):
                    try_cnt += 1
            print()
            self.slave = new_address
            if not self.try_new_slave():
                self.slave = old_address
        else:
            border_print("Адрес датчика не изменен", "#")

    def try_new_slave(self):
        err_cnt = 0
        while err_cnt < 10:
            try:
                get_data = self.execute(self.slave, mb_def.READ_HOLDING_REGISTERS, 249, 1)
                if get_data[0] == self.slave:
                    self.is_connect = True
                    border_print("Новый адрес датчика записан", "#")
                    break
            except (socket.timeout, modbus_tk.modbus_tcp.ModbusInvalidMbapError):
                self.is_connect = False
            err_cnt += 1
        if not self.is_connect:
            border_print("Запись не удалась", "!")
            return False
        return True


def get_int(message="", name="", minimum=0, maximum=65535, zero_exit=False):
    """
    Функция проверяет введенные пользователем данные на int и принадлежность к диапазону
    """
    while True:
        try:
            line = input(message)
            if not line:
                return None
            usr_int = int(line)
            if zero_exit and usr_int == 0:
                return "quit"
            elif not zero_exit and usr_int == 0:
                return None
            if maximum < usr_int or usr_int < minimum:
                raise _RangeError("{0} не в диапазоне от {1} до {2}.".format(name, minimum, maximum))
            return usr_int
        except _RangeError as err:
            border_print("ERROR:" + str(err), "!")
        except ValueError:
            border_print("ERROR: {0} не число".format(name), "!")


def programm_exit():
    """
    Закрываем порты перед окончанием программы
    """
    global port_obj
    if port_obj is not None:
        port_obj.close()
        if not port_obj.check_ports():
            border_print(["Программа завершена", " нажмите [ Ввод ]"], "*")
    else:
        border_print(["Программа завершена", " нажмите [ Ввод ]"], "*")
    input()


def border_print(message, hor_sym, vert_sym=None):
    """
    Делаем рамку вокруг сообщения
    """
    print()
    if vert_sym is None:
        vert_sym = hor_sym
    if type(message) == list:
        max_len = 0
        for mess in message:
            if len(mess) > max_len:
                max_len = len(mess)
        print(hor_sym * (max_len + 4))
        for num, mess in enumerate(message):
            if num == 0:
                print(vert_sym + " " * (((max_len + 2) - len(mess)) // 2) + mess +
                      " " * (((max_len + 2) - len(mess)) - ((max_len + 2) - len(mess)) // 2) + vert_sym)
            else:
                print(vert_sym + " " + mess + " " * (max_len - len(mess) + 1) + vert_sym)
        print(hor_sym * (max_len + 4))
    else:
        print(hor_sym * (len(message) + 4))
        print(vert_sym + " " + message + " " + vert_sym)
        print(hor_sym * (len(message) + 4))


def get_bool(message="\nСконфигурировать новый датчик? (да/д/yes/y): ", lst=None):
    """
    Возвращаем подтверждение от пользователя
    """
    if lst is None:
        lst = ["да", "д", "y", "yes"]
    yes = frozenset(lst)
    line = input(message)
    return line.lower() in yes


def get_host():
    """
    Проверяем корректность введенного адреса
    """
    correct_host = re.compile("([0-9]{1,3}[.]){3}[0-9]{1,3}")
    while True:
        host = input("\nВведите IP адрес:"
                     "\n\t(пустое поле или 0 - выход из программы): ")
        if not host or host == "0":
            return "quit"
        if re.match(correct_host, host):
            return host
        else:
            border_print("Ввод некорректен", "!")


def wait_esc():
    """
    Ожидание esc для прерывания процесса
    """
    global port_search
    print("\nНажмите [ Esc ] чтобы прервать процесс поиска\n")
    try:
        keyboard.wait("esc")
        port_search = False
    except KeyError:
        port_search = False


def main():
    global port_obj, sock, port_search
    border_print("КОНФИГУРАТОР ДАТЧИКА ДАВЛЕНИЯ 415М-ДИ", "~", "|")
    mode = get_int(message="\nВыберите способ подключения и нажмите [ Ввод ]:"
                           "\n\t1 - Modbus RTU (через COM порт)"
                           "\n\t2 - Modbus TCP (через IP адрес)"
                           "\n\t(пустое поле или 0 - выход из программы): ",
                   name="способ подключения", minimum=1, maximum=2, zero_exit=True)
    prog_start = True
    if mode is None or mode == "quit":
        pass
    elif mode == 1:
        ports = list_ports.comports()
        str_ports = ["СПИСОК ДОСТУПНЫХ ПОРТОB:"]
        for port in ports:
            str_ports.append(str(port))
        border_print(str_ports, "~", "|")

        while prog_start:
            port = get_int(message="\nВведите номер COM порта и нажмите [ Ввод ]"
                                   "\n\t(пустое поле для автоматического поиска, 0 - выход из программы): ",
                           name="номер COM порта", minimum=1, maximum=4096, zero_exit=True)
            if port == "quit":
                break
            port_obj = Port(port)
            if port_obj.check_ports():
                while True:
                    slave = get_int("\nВведите адрес датчика давления и нажмите [ Ввод ]"
                                    "\n\t(пустое поле для автоматического поиска, 0 - выход из программы): ",
                                    name="адрес датчика давления", minimum=1, maximum=247, zero_exit=True)
                    if slave == "quit":
                        break
                    device_obj = Device(port_obj, slave)
                    if device_obj.check_connect():
                        new_address = get_int("\nВведите новый адрес датчика давления и нажмите [ Ввод ]"
                                              "\n\t(пустое поле или 0 - оставить прежний): ",
                                              name="адрес датчика давления", minimum=1, maximum=247)
                        device_obj.write_slave(new_address)
                    if not prog_start == get_bool():
                        break
                    else:
                        port_obj.close()
                        port_obj = Port(port)
                        if not port_obj.check_ports():
                            break
                break
    else:
        while prog_start:
            host = get_host()
            if host == "quit":
                break
            port = get_int("\nВведите номер порта  и нажмите [ Ввод ]"
                           "\n\t(пустое поле для ввода диапазона, 0 - выход из программы): ",
                           name="номер порта", minimum=1, maximum=65535, zero_exit=True)
            try:
                if port is None:
                    start_range = get_int("\nВведите начало диапазона и нажмите [ Ввод ]"
                                          "\n\t(пустое поле или 0 - выход из программы): ",
                                          name="начало диапазона", minimum=1, maximum=65535, zero_exit=True)
                    if start_range is None or start_range == "quit":
                        break
                    end_range = get_int("\nВведите окончание диапазона и нажмите [ Ввод ]"
                                        "\n\t(пустое поле или 0 - выход из программы): ",
                                        name="окончание диапазона",
                                        minimum=start_range, maximum=65535, zero_exit=True)
                    if end_range is None or end_range == "quit":
                        break
                    ports = range(start_range, end_range+1)
                    thread1 = Thread(target=wait_esc, daemon=True)
                    thread1.start()
                    print("\nПробуем подключиться к порту: ", end="")
                    cnt_ports = 0
                    port_search = True
                    for port in ports:
                        if not port_search:
                            break
                        cnt_ports += 1
                        print(str(port), end="")
                        print("\b" * len(str(port)), end="", flush=True)

                        sock = Sock(host, port, test=True)
                        if sock.check_connect():
                            while True:
                                slave = get_int("\nВведите адрес датчика давления и нажмите [ Ввод ]"
                                                "\n\t(пустое поле для автоматического поиска, "
                                                "0 - выход из программы): ",
                                                name="адрес датчика давления", minimum=1, maximum=247, zero_exit=True)
                                if slave == "quit":
                                    prog_start = False
                                    break
                                device_tcp = TcpDevice(host, port, slave)
                                if device_tcp.check_connect():
                                    new_address = get_int("\nВведите новый адрес датчика давления и нажмите [ Ввод ]"
                                                          "\n\t(пустое поле или 0 - оставить прежний): ",
                                                          name="адрес датчика давления", minimum=1, maximum=247)
                                    device_tcp.write_slave(new_address)
                                if not prog_start == get_bool():
                                    prog_start = False
                                    break
                            sock = None
                            break
                    if cnt_ports == len(ports):
                        cnt_ports = 0
                        print()
                        border_print("Подключиться к порту в заданном диапазоне не удалось", "!")
                        continue
                    break
                elif port == "quit":
                    break
                else:
                    sock = Sock(host, port)
            finally:
                if sock is not None and sock.check_connect():
                    while True:
                        slave = get_int("\nВведите адрес датчика давления и нажмите [ Ввод ]"
                                        "\n\t(пустое поле для автоматического поиска, 0 - выход из программы): ",
                                        name="адрес датчика давления", minimum=1, maximum=247, zero_exit=True)
                        if slave == "quit":
                            prog_start = False
                            break
                        device_tcp = TcpDevice(host, port, slave)
                        if device_tcp.check_connect():
                            new_address = get_int("\nВведите новый адрес датчика давления и нажмите [ Ввод ]"
                                                  "\n\t(пустое поле или 0 - оставить прежний): ",
                                                  name="адрес датчика давления", minimum=1, maximum=247)
                            device_tcp.write_slave(new_address)
                        if not prog_start == get_bool():
                            prog_start = False
                            break
    programm_exit()


if __name__ == "__main__":
    main()
