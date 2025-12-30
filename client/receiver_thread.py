import network_manager
import threading
import json
import socket

class ReceiverThread(threading.Thread): # jako osobny watek
    def __init__(self, sock, queue, controller):
        super().__init__(daemon=True)
        self.sock = sock
        self.queue = queue
        self.controller = controller
        self.running = True

    def run(self):
        print("receiver_thread - wątek odbiorczy wystartował")
        while self.running:
            try:
                response_json_string = network_manager.receive_data_and_process(self.sock)
                
                if response_json_string is False: # rozłączenie z network_manager.receive_data_and_process
                    print("BŁĄD - receiver_thread.run : serwer zerwał połączenie (brak danych)")
                    self.controller.network_queue.put(
                        json.dumps({"type": "network_error", "reason": "Serwer rozłączył się."}) # wiadomosc do GUI ze klienta rozlaczylo
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
        #print("receiver_thread - wątek odbiorczy zakończony")

    def stop(self):
        self.running = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR) 
            self.sock.close() # zamyka socket
        except:
            pass