import network_manager
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
        while self.running:
            try:
                response_json_string = network_manager.receive_data_and_process(self.sock)
                
                if response_json_string is False: 
                    self.controller.network_queue.put(
                        json.dumps({"type": "network_error", "reason": "Serwer rozłączył się."}) 
                    )
                    break
                    
                if response_json_string is not None:
                    self.queue.put(response_json_string) # wiadomosc przesylana do GUI do obslugi w handlerach
                    
                # jeśli response_json_string is None - odebrano niekompletną wiadomość lub Timeout
                
            except Exception as e:
                print(f"BŁĄD - receiver_thread : {e}")
                self.controller.network_queue.put(
                        json.dumps({"type": "network_error", "reason": f"Błąd odbioru: {e}"})
                    )
                break
        self.running = False

    def stop(self):
        self.running = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR) 
            self.sock.close() 
        except:
            pass