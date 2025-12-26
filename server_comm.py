import socket
import json

def connect_to_server(ip, port): #Tworzy i zwraca POŁĄCZONY socket.

    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((ip, port))
        return client_socket
        
    except Exception as e:
        print(f"BŁĄD connect_to_server : Nie udało się połączyć: {e}")
        return None
    
def send_json(sock, data): #Wysyła słownik Pythona jako wiadomość JSON zakończoną znakiem nowej linii
    
    try:
        json_message = json.dumps(data)
        message = json_message + '\n'
        sock.sendall(message.encode('utf-8'))
        return True
    except Exception as e:
        return False

#  bufor do obsługi danych w jednym ciągłym strumieniu
CLIENT_SOCKET_BUFFER = ""

def get_next_message():
    global CLIENT_SOCKET_BUFFER
    if '\n' in CLIENT_SOCKET_BUFFER:
        line, CLIENT_SOCKET_BUFFER = CLIENT_SOCKET_BUFFER.split('\n', 1)
        return line
    return None

def receive_data_and_process(sock, buffer_size=4096):
    """
    Odbiera dane, dodaje je do bufora i zwraca pierwszą pełną wiadomość JSON.
    Zwraca string JSON, None w przypadku braku pełnej wiadomości lub False w przypadku rozłączenia.
    """
    global CLIENT_SOCKET_BUFFER
    
    try:
        data_bytes = sock.recv(buffer_size)
        if not data_bytes:
            print("Serwer zerwał połączenie.")
            return False 
            
        data_string = data_bytes.decode('utf-8')
        
        CLIENT_SOCKET_BUFFER += data_string
        return get_next_message()
            
    except socket.timeout:
        # możliwe, jeśli gniazdo jest nieblokujące
        return None 
    except Exception as e:
        print(f"BŁĄD sieciowy podczas odbierania: {e}")
        return False 

# funkcja będzie używana tylko  podczas logowania
def receive_first_message_blocking(sock, buffer_size=4096):
    global CLIENT_SOCKET_BUFFER
    # Resetowanie globalnego bufora przed użyciem
    CLIENT_SOCKET_BUFFER = "" 
    
    local_buffer = "" 
    
    print("[COMM] BLOKUJĄCY ODBIÓR: Wystartowano.")
    
    while True:
        try:
            data_bytes = sock.recv(buffer_size)
            
            if not data_bytes:
                print("[COMM] BLOKUJĄCY ODBIÓR: Serwer zamknął połączenie.")
                return None
            
            data_string = data_bytes.decode('utf-8')
            local_buffer += data_string
            
            print(f"[COMM] BLOKUJĄCY ODBIÓR: Otrzymano dane (długość bufora: {len(local_buffer)})")

            if '\n' in local_buffer:
                line, remaining_data = local_buffer.split('\n', 1)
                
                CLIENT_SOCKET_BUFFER = remaining_data
                print(f"[COMM] BLOKUJĄCY ODBIÓR: Znaleziono pełną wiadomość! Zwracam: {line[:50]}...")
                
                return line
            
        except Exception as e:
            print(f"[COMM] BLOKUJĄCY ODBIÓR: BŁĄD NIEOCZEKIWANY: {e}")
            return None
