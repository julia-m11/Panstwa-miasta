import server_comm
import threading
import json
import socket

class ReceiverThread(threading.Thread):
    def __init__(self, sock, queue, controller):
        super().__init__(daemon=True)
        self.sock = sock
        self.queue = queue
        self.controller = controller
        self.running = True

    def run(self):
        print("[RECEIVER] Wątek odbiorczy wystartował.")
        while self.running:
            try:
                response_json_string = server_comm.receive_data_and_process(self.sock)
                
                if response_json_string is False:
                    # rozłączenie z server_comm.receive_data_and_process
                    print("[RECEIVER] Serwer zerwał połączenie (brak danych).")
                    self.controller.network_queue.put(
                        json.dumps({"type": "network_error", "reason": "Serwer rozłączył się."})
                    )
                    break
                    
                if response_json_string is not None:
                    self.queue.put(response_json_string)
                    
                # jeśli response_json_string jest None, to znaczy, że 
                # odebrano niekompletną wiadomość (jest w buforze) lub Timeout
                
            except Exception as e:
                print(f"[RECEIVER ERROR] {e}")
                self.controller.network_queue.put(
                        json.dumps({"type": "network_error", "reason": f"Krytyczny błąd odbioru: {e}"})
                    )
                break
        self.running = False
        print("[RECEIVER] Wątek odbiorczy zakończony.")

    def stop(self):
        self.running = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()
        except:
            pass