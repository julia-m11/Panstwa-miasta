import socket
import json

CLIENT_SOCKET_BUFFER = ""   

def connect_to_server(ip, port): 
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #  tcp
        client_socket.connect((ip, port))
        client_socket.settimeout(1.0)
        return client_socket 
        
    except Exception as e:
        print(f"BŁĄD - connect_to_server : Nie udało się połączyć i utworzyć socketu: {e}")
        return None
    
def send_json(sock, data): 
    try:
        json_message = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        message = json_message + '\n' 
        sock.sendall(message.encode('utf-8'))
        return True
    except Exception as e:
        return False

def get_next_message():
    global CLIENT_SOCKET_BUFFER

    if '\n' in CLIENT_SOCKET_BUFFER:
        line, CLIENT_SOCKET_BUFFER = CLIENT_SOCKET_BUFFER.split('\n', 1) 
        return line
    return None # w przypadku  braku pelnej wiadomosci

def receive_data_and_process(sock, buffer_size=4096):
    global CLIENT_SOCKET_BUFFER
    
    try:
        data_bytes = sock.recv(buffer_size)
        if not data_bytes:
            print("BŁĄD - receive_data_and_process : Serwer zerwał połączenie.")
            return False 
            
        data_string = data_bytes.decode('utf-8')
        
        CLIENT_SOCKET_BUFFER += data_string
        return get_next_message()
            
    except socket.timeout:
        return None 
    except Exception as e:
        print(f"BŁĄD - receive_data_and_process : blad podczas odbierania: {e}")
        return False # gdy sie rozlaczy

def receive_first_message_blocking(sock, buffer_size=4096): # funkcja używana tylko podczas logowania
    global CLIENT_SOCKET_BUFFER
    CLIENT_SOCKET_BUFFER = "" 
    
    local_buffer = "" 
    
    while True:
        try:
            data_bytes = sock.recv(buffer_size)
            
            if not data_bytes:
                print("BŁĄD - receive_first_message_blocking : Serwer zamknął połączenie.")
                return None
            
            data_string = data_bytes.decode('utf-8')
            local_buffer += data_string

            if '\n' in local_buffer:
                line, remaining_data = local_buffer.split('\n', 1)
                CLIENT_SOCKET_BUFFER = remaining_data
                return line
        except socket.timeout:
            continue
            
        except Exception as e:
            print(f"BŁĄD - receive_first_message_blocking : {e}")
            return None
