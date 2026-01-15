import tkinter as tk
from tkinter import ttk
import network_manager
import json
import threading
from queue import Queue
from tkinter import messagebox
import socket
from receiver_thread import ReceiverThread

# ----------------------poszczegolne okna--------------------------------------

class Log_in_window(tk.Frame):
    
    def __init__(self, parent, kontroler):
        tk.Frame.__init__(self, parent)
        self.kontroler = kontroler 
        self.config(bg='lightgray') 

        # ----------------------elementy okna-----------------

        title = tk.Label(self, text="MENU GŁÓWNE GRY", font=("Arial", 24, "bold"), bg = "lightblue")
        title.pack(pady=50)

        #---------------pole na nick---------------------------

        etykieta_nick = ttk.Label(self, text="Wprowadź swój nick:", font=("Arial", 10))
        etykieta_nick.pack(pady=(10, 10)) 
        self.pole_nick = ttk.Entry(self, width=25)
        self.pole_nick.pack(padx=20, pady=5)

        #---------------pole na ip serwera--------------

        etykieta_ip = ttk.Label(self, text="Wprowadź adres ip serwera:", font=("Arial", 10))
        etykieta_ip.pack(pady=(10, 10)) 
        self.pole_ip = ttk.Entry(self, width=25)
        self.pole_ip.pack(padx=20, pady=5)

        #---------------pole na port------------------

        etykieta_port = ttk.Label(self, text="Wprowadź port:", font=("Arial", 10))
        etykieta_port.pack(pady=(10, 10)) 
        self.pole_port = ttk.Entry(self, width=25)
        self.pole_port.pack(padx=20, pady=5)

        self.connect_button = ttk.Button(
            self, text="POŁĄCZ",
            command=self.connect_and_save
        )
        self.connect_button.pack(pady=10, padx=20)
        
    def connect_and_save(self):
        
        nick = self.pole_nick.get().strip()
        ip_serwera = self.pole_ip.get().strip()
        port_serwera = self.pole_port.get().strip() 
        
        if not (nick and ip_serwera and port_serwera):
            messagebox.showerror(
                "Błąd Wypełnienia Pól", 
                "Wszystkie pola muszą być wypełnione (Nick, IP i Port), aby nawiązać połączenie." 
            )
            return

        try:
            port_int = int(port_serwera) # konwersja na int i zapisanie wyniku
        except ValueError:
            messagebox.showerror(
                "Błąd Portu", 
                "Port musi być liczbą całkowitą."
            )
            return 
        
        try:
            socket.inet_aton(ip_serwera) 
        except socket.error:
            messagebox.showerror(
                "Błąd IP", 
                f"Nieprawidłowy format adresu IP: '{ip_serwera}'."
            )
            return

        self.kontroler.dane_gry['nick'] = nick
        self.connect_button.config(state='disabled') 
        
        print(f"Próba połączenia z {ip_serwera}:{port_int} jako {nick}...")

        threading.Thread( # aby okno gry nie zamarlo czekajac
            target=self.initiate_connection_and_login, 
            args=(nick, ip_serwera, port_int), 
            daemon=True
        ).start()

    def initiate_connection_and_login(self, nick, ip_serwera, port_serwera_int):
            
        self.kontroler.nawiaz_polaczenie_z_serwerem(ip_serwera, port_serwera_int)
    
        if self.kontroler.socket_polaczenia:
            print("Połączenie udane, wysyłam nick do serwera...")
            sock = self.kontroler.socket_polaczenia
            
            dane_do_wyslania = {
                "type": "connecting_with_server", "nick": nick}
            network_manager.send_json(sock, dane_do_wyslania) # wysyłka z tego wątku
            
            # ODBIERAMY BLOKUJĄCO
            try:
                first_json_response = network_manager.receive_first_message_blocking(sock)
                
                if first_json_response:
                    
                    self.kontroler.network_queue.put(first_json_response)
                    data = json.loads(first_json_response)
                    if data.get("type") == "nick_accepted":
                        self.kontroler.start_receiving_data() 
                    
                else: # brak odpowiedzi lub rozłączenie
                    blad = json.dumps({"type": "network_error", "reason": "Serwer rozłączył się po wysłaniu nicku."})
                    self.kontroler.network_queue.put(blad)
                    
            except Exception as e:
                print(f"BŁĄD - initiate_connection_and_login : Błąd przy odbieraniu pierwszej odpowiedzi: {e}")
                blad = json.dumps({"type": "network_error", "reason": f"Błąd komunikacji: {e}"})
                self.kontroler.network_queue.put(blad)
        else:
            print("BŁĄD - initiate_connection_and_login : Połączenie nieudane")

# -------------------------------okno lobby--------------------------------------------

class Lobby(tk.Frame):
    
    def __init__(self, parent, kontroler):
        tk.Frame.__init__(self, parent)
        self.kontroler = kontroler
        self.config(bg='lightblue')
        self.is_joined = False

        #timer dla countdown
        self.countdown_id = None    # ID timera Tkinter (dla self.after)
        self.remaining_time = 0     # Czas pozostały w sekundach
        self.countdown_active = False # Flaga, czy odliczanie jest w toku

        #timer dla idle
        self.idle_timeout_id = None # ID timera do pytania o dalsze czekanie
        self.IDLE_TIMEOUT_MS = 120000 # 2 minuty = 120 000 ms
        self.is_countdown_active = False

        # Etykieta statusu gry
        self.game_status_label = ttk.Label(self, text="", font=("Arial", 20), background='lightgray')
        self.game_status_label.pack(pady=(40,20))

        # Etykieta komunikatów dla gracza
        self.player_message_label = ttk.Label(self, text="", font=("Arial", 14), background='lightblue')
        self.player_message_label.pack(pady=(10,10))

        self.countdown_label = ttk.Label(self, text="", font=("Arial", 20), foreground='red')
        self.countdown_label.pack(pady=(10,10))

    # --- KONTENER PRZYCISKÓW WYBORU ---
        
        self.buttons_frame = ttk.Frame(self)
        #self.buttons_frame.pack(pady=30)
            
        # Przycisk 1: Dołącz od nastepnej rundy - in_round
        self.btn_join_next_round = ttk.Button(
            self.buttons_frame, 
            text="Dołącz od następnej rundy",
            command=lambda: self.send_lobby_choice("WANT_TO_PLAY_IN_NEXT_ROUND")
        )
        
        # Przycisk 2: Czekaj na nową grę - in_round
        self.btn_queue = ttk.Button(
            self.buttons_frame, 
            text="Czekaj na nową grę",
            command=lambda: self.send_lobby_choice("WANT_TO_QUEUE")
        )

        # Przycisk 3: Dołacz do nowej gry - lobby
        self.btn_join_game = ttk.Button(
            self.buttons_frame, 
            text="Dołącz do nowej gry",
            command=lambda: self.send_lobby_choice("WANT_TO_PLAY")
        )

        self.hide_buttons() 

    def start_idle_timer(self):
        self.cancel_idle_timer()
        self.idle_timeout_id = self.after(self.IDLE_TIMEOUT_MS, self.force_quit_on_timeout) 
        print(f"[IDLE TIMER] Timer automatycznego wyjścia wystartował ({self.IDLE_TIMEOUT_MS/1000}s).")

    def cancel_idle_timer(self):
        """Anuluje timer pytania o kontynuację."""
        if self.idle_timeout_id:
            self.after_cancel(self.idle_timeout_id)
            self.idle_timeout_id = None
            print("[IDLE TIMER] Timer pytania o kontynuację anulowany.")   

    def force_quit_on_timeout(self): 
        # wyświetla komunikat o braku graczy po upływie czasu oczekiwania i automatycznie zamyka aplikację.
        self.idle_timeout_id = None 
        
        messagebox.showinfo(
            "Brak Graczy", 
            "Niestety, nikt nie dołączył do Lobby w ciągu 2 minut. Aplikacja zostanie zamknięta."
        )
        
        self.kontroler.on_closing() 
        
    def start_countdown(self, seconds):
        if self.countdown_id:
            self.after_cancel(self.countdown_id) # anuluj poprzedni timer, jeśli był
            
        self.remaining_time = seconds
        self.countdown_active = True
        self.countdown_label.config(text=f"START GRY ZA: {self.remaining_time}s")
        self.countdown_label.pack(pady=10)
        
        self.update_countdown_gui()

    def update_countdown_gui(self):
        """Cyklicznie aktualizuje licznik w dół."""
        if not self.countdown_active or self.remaining_time <= 0:
            self.countdown_label.config(text="STARTUJEMY!")
            self.countdown_active = False
            return

        self.countdown_label.config(text=f"START GRY ZA: {self.remaining_time}s")
        self.remaining_time -= 1
        
        self.countdown_id = self.after(1000, self.update_countdown_gui)

    def stop_countdown(self):
        if self.countdown_id:
            self.after_cancel(self.countdown_id)
        self.countdown_active = False
        self.countdown_label.pack_forget() 

    def show_lobby(self):
        self.kontroler.wyslij_wiadomosc_do_serwera({"type": "REQUEST_GAME_INFO"})

    def hide_buttons(self):
        self.btn_join_game.grid_forget()
        self.btn_join_next_round.grid_forget()
        self.btn_queue.grid_forget()
        
    def show_buttons(self, mode, current_round=0): #tu zmiana !!!
        self.hide_buttons() 
        self.buttons_frame.pack_forget()
        
        if mode == 'GAME_OVER':
            #self.buttons_frame.pack_forget()
            return 

        #self.buttons_frame.pack(pady=30) 

        if mode == 'IN_ROUND':
            self.buttons_frame.pack(pady=30)

            if current_round < 5:
                self.btn_join_next_round.grid(row=0, column=0, padx=10)
                self.btn_join_next_round.config(state='normal')

            #self.btn_join_next_round.grid(row=0, column=0, padx=10)
            self.btn_queue.grid(row=0, column=1, padx=10)
            #self.btn_join_next_round.config(state='normal')
            self.btn_queue.config(state='normal')
        
        elif mode == 'LOBBY':
            # Tutaj nie wyświetlamy już btn_join_game, bo wysyłamy WANT_TO_PLAY automatycznie
            pass
            
    def send_lobby_choice(self, choice_type):
        self.kontroler.wyslij_wiadomosc_do_serwera({"type": choice_type})
        
        self.btn_join_game.config(state='disabled')
        self.btn_queue.config(state='disabled')
        self.btn_join_next_round.config(state='disabled')
        #self.player_message_label.config(text="Czekam na potwierdzenie statusu od serwera...")

        if choice_type == "WANT_TO_PLAY":
        
        # timer IDLE startuje tylko, jeśli nie trwa countdown
            if not self.is_countdown_active:
                self.start_idle_timer()
            else:
                self.cancel_idle_timer()
                print("[IDLE TIMER] Kliknięcie w trakcie COUNTDOWN. Zablokowano start timera IDLE.")

# -------------------------------- okno gry -------------------------------------------------

class Game_window(tk.Frame):
    def __init__(self, parent, kontroler):
        tk.Frame.__init__(self, parent)
        self.kontroler = kontroler
        self.config(bg='white')

        self.info_frame = tk.Frame(self, bg='lightgray')
        self.info_frame.pack(fill="x", pady=10)

        self.round_label = tk.Label(self.info_frame, text="Runda: 1/5", font=("Arial", 12))
        self.round_label.pack(side="left", padx=20)

        self.letter_label = tk.Label(self.info_frame, text="LITERA: -", font=("Arial", 20, "bold"), fg="blue")
        self.letter_label.pack(side="left", expand=True)

        self.points_label = tk.Label(self.info_frame, text="Twoje punkty: 0", font=("Arial", 12, "bold"))
        self.points_label.pack(side="right", padx=20)

        self.table_frame = tk.Frame(self, bg='white')
        self.table_frame.pack(pady=40)

        self.kategorie = ["Państwo", "Miasto", "Roślina", "Zwierzę", "Rzecz"]
        self.entries = {}

        for i, kat in enumerate(self.kategorie):
            lbl = tk.Label(self.table_frame, text=kat, font=("Arial", 10, "bold"), bg='white')
            lbl.grid(row=0, column=i, padx=5, pady=5)
            
            ent = ttk.Entry(self.table_frame, width=15)
            ent.grid(row=1, column=i, padx=5, pady=5)
            self.entries[kat.lower()] = ent

        self.btn_stop = ttk.Button(self, text="ZATWIERDŹ", command=lambda: self.send_answers(triggered_by_user=True))
        self.btn_stop.pack(pady=20)

        self.warning_label = tk.Label(self, text="", font=("Arial", 14, "bold"), fg="darkorange", bg='white')
        self.warning_label.pack(pady=5)
        
        self.auto_send_timer_id = None
        self.answers_sent = False #zapobieganie wysylania dwa razy

    def start_round_gui(self, round_num, letter, points):
        self.answers_sent = False
        """Metoda wywoływana przez App przy ROUND_START"""
        self.round_label.config(text=f"Runda: {round_num}/5")
        self.letter_label.config(text=f"LITERA: {letter}")
        self.points_label.config(text=f"Twoje punkty: {points}")
        
        # Odblokowanie i czyszczenie pól
        for entry in self.entries.values():
            entry.config(state='normal')
            entry.delete(0, tk.END)
        self.btn_stop.config(state='normal')

        self.warning_label.config(text="") # Czyścimy ostrzeżenie
        if self.auto_send_timer_id:
            self.after_cancel(self.auto_send_timer_id)
            self.auto_send_timer_id = None

    def send_answers(self, triggered_by_user=False):
        """Pobiera dane i wysyła do serwera. is_first=True jeśli kliknął przycisk."""
        
        if self.answers_sent:
            return 
        
        self.answers_sent = True

        self.btn_stop.config(state='disabled')
        for entry in self.entries.values():
            entry.config(state='disabled')

        if self.auto_send_timer_id:
            print("[DEBUG] Anuluję timer odliczania, bo odpowiedzi zostały wysłane.")
            self.after_cancel(self.auto_send_timer_id)
            self.auto_send_timer_id = None

        odpowiedzi = {kat: ent.get() for kat, ent in self.entries.items()}
        self.kontroler.wyslij_wiadomosc_do_serwera({
            "type": "ROUND_END_ANSWERS",
            "answers": odpowiedzi
        })
        
        if triggered_by_user: # w zaleznosci jak zosttaly wyslane wiadomosci
            self.warning_label.config(
                text="Odpowiedzi wysłane. Czekanie na innych...",
                fg="green"
            )
        else:
            self.warning_label.config(
                text="Czas minął. Odpowiedzi wysłane automatycznie.",
                fg="green"
            )
        #self.warning_label.config(text="Odpowiedzi wysłane. Czekanie na wyniki...", fg="green")
        #print(f"[DEBUG] Wysłano ROUND_END_ANSWERS. is_first={is_first}")

    def activate_time_warning(self, seconds):
        """Uruchamia licznik po tym, jak ktoś inny skończył."""
        if self.answers_sent:
            print("[DEBUG] Otrzymano TIME_WARNING, ale odpowiedzi są już wysłane. Ignoruję.")
            return # Już wysłaliśmy odpowiedzi, ignorujemy
        self.btn_stop.config(state='disabled')
        self.remaining_warning_time = seconds
        self.update_warning_timer()

    def update_warning_timer(self):
        if self.remaining_warning_time > 0:
            self.warning_label.config(text=f"Ktoś skończył! Masz {self.remaining_warning_time}s!")
            self.remaining_warning_time -= 1
            self.auto_send_timer_id = self.after(1000, self.update_warning_timer)
        else:
            self.warning_label.config(text="CZAS MINĄŁ!")
            self.send_answers(triggered_by_user=False) #automatyczne wysylanie

# ------------------------------okno wynikow---------------------------------------------

class Result_window(tk.Frame):
    def __init__(self, parent, kontroler):
        tk.Frame.__init__(self, parent)
        self.kontroler = kontroler
        self.config(bg='#f0f0f0')
        self.quit_timer_id = None

        tk.Label(self, text="KONIEC GRY - WYNIKI", font=("Arial", 26, "bold"), bg='#f0f0f0').pack(pady=30)

        self.personal_result_label = tk.Label(self, text="", font=("Arial", 18), bg='#f0f0f0', fg="blue")
        self.personal_result_label.pack(pady=10)

        tk.Label(self, text="TOP 3 GRACZY:", font=("Arial", 16, "underline"), bg='#f0f0f0').pack(pady=(20, 10))
        self.ranking_label = tk.Label(self, text="", font=("Courier", 14), bg='white', relief="sunken", width=40, height=5)
        self.ranking_label.pack(pady=10)

        # Label informujący o powrocie do lobby
        self.timer_label = tk.Label(self, text="", font=("Arial", 12), fg="darkgreen", bg='#f0f0f0')
        self.timer_label.pack(pady=20)

        btn_frame = tk.Frame(self, bg='#f0f0f0')
        btn_frame.pack(pady=20)

        self.btn_join_new = ttk.Button(
            btn_frame, 
            text="Dołącz do nowej gry", 
            command=self.return_to_lobby
        )
        self.btn_join_new.grid(row=0, column=0, padx=10)

        # przycisk wyjścia
        self.btn_quit = ttk.Button(btn_frame, text="Wyjdź z gry", command=self.kontroler.on_closing)
        self.btn_quit.grid(row=0, column=1, padx=10)

    def show_results(self, data):
        your_place = data.get("your_place", "?")
        your_total = data.get("total_points", 0)
        top_3 = data.get("top_3", [])

        self.personal_result_label.config(
            text=f"Zająłeś/aś {your_place} miejsce z {your_total} punktami!"
        )

        ranking_text = ""
        for i, player in enumerate(top_3):
            ranking_text += f"{i+1}. {player['nick']} - {player['points']} pkt\n"
        
        self.ranking_label.config(text=ranking_text)
        
        # Startujemy odliczanie do POWROTU DO LOBBY
        self.start_return_timer(20)

    def start_return_timer(self, seconds):
        if self.quit_timer_id:
            self.after_cancel(self.quit_timer_id)
            
        if seconds > 0:
            self.timer_label.config(text=f"Powrót do poczekalni za: {seconds} s...")
            self.quit_timer_id = self.after(1000, lambda: self.start_return_timer(seconds - 1))
        else:
            print("[GUI] Czas wyświetlania wyników minął. Wracam do Lobby.")
            self.return_to_lobby()

    def return_to_lobby(self):
        """Zatrzymuje timer i wraca do Lobby."""
        if self.quit_timer_id:
            self.after_cancel(self.quit_timer_id)
            self.quit_timer_id = None
        
        # Przełączamy na Lobby - to automatycznie wywoła REQUEST_GAME_INFO w App.pokaz_ekran
        self.kontroler.pokaz_ekran(Lobby)
    
# ------------------------------glowne okno----------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Państwa-miasta")
        self.geometry("800x600")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.receiver_thread = None

        self.network_queue = Queue() 
        self.socket_polaczenia = None 
        self.sprawdz_kolejke_sieciowa() 
        self.current_round_active = None
        #self.round_start_received = False
        
        #-----------------Gui-------------------
        
        self.dane_gry = {} 

        kontener = ttk.Frame(self)
        kontener.pack(side="top", fill="both", expand=True)
        kontener.grid_rowconfigure(0, weight=1)
        kontener.grid_columnconfigure(0, weight=1)

        self.ekrany = {}
        
        for F in (Log_in_window, Lobby, Game_window, Result_window):
            ekran_name = F.__name__
            frame = F(parent=kontener, kontroler=self) 
            self.ekrany[ekran_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.pokaz_ekran(Log_in_window)

    def start_receiving_data(self): # tworzy watek odbiorczy
        if self.socket_polaczenia and not self.receiver_thread:
            self.receiver_thread = ReceiverThread( 
                sock=self.socket_polaczenia,
                queue=self.network_queue,
                controller=self
            )
            self.receiver_thread.start() # startujemy ciągły odbiór
            print("start_receiving_data : wątek odbiorczy wystartował")

        
    def pokaz_ekran(self, klasa_ekranu):
        nazwa = klasa_ekranu.__name__
        frame = self.ekrany[nazwa]
        frame.tkraise()

        if klasa_ekranu == Lobby:
            frame.show_lobby() # Wywołaj nową metodę w Lobby
        
    def on_closing(self): #przy wyjsciu z aplikacji
        if self.socket_polaczenia:
            try:
                self.socket_polaczenia.close()
                print("Połączenie sieciowe zamknięte.")
            except Exception as e:
                print(f"Błąd przy zamykaniu gniazda: {e}")
        self.destroy()


    def wyslij_wiadomosc_do_serwera(self, dane):
        print(f"Wysylam wiadomosc - {dane}")
        if self.socket_polaczenia:
            # wysłanie w osobnym wątku
            threading.Thread(
                target=network_manager.send_json, 
                args=(self.socket_polaczenia, dane),
                daemon=True
            ).start()
        else:
            messagebox.showerror("Błąd", "Brak aktywnego połączenia z serwerem.")
        
    def nawiaz_polaczenie_z_serwerem(self, host, port):

        socket_polaczenia = network_manager.connect_to_server(host, port)
        
        if socket_polaczenia:
            self.socket_polaczenia = socket_polaczenia
            print("nawiaz_polaczenie_z_serwerem : Pomyślnie połączono z serwerem.")
            
        else:
            blad = json.dumps({"type": "network_error", "reason": "Brak połączenia."})
            self.network_queue.put(blad)
            
    def sprawdz_kolejke_sieciowa(self):

        from queue import Empty 
        
        try:
            komunikat = self.network_queue.get_nowait()
            self.obsluz_odpowiedz_serwera(komunikat)
        except Empty:
            pass 
        except Exception as e:
            print(f"[ERROR GUI] Krytyczny błąd podczas sprawdzania kolejki: {e}") 

        self.after(100, self.sprawdz_kolejke_sieciowa)

    def obsluz_odpowiedz_serwera(self, odpowiedz_json_string):
    
        try:
            data = json.loads(odpowiedz_json_string)
            print(f"dostalam wiadomosc - {data}")
            message_type = data.get("type")
            
            handlers = {
                "network_error": self.handle_network_error,
                "nick_accepted" : self.handle_nick_accepted,
                "nick_rejected" : self.handle_nick_rejected,
                "GAME_STATUS" : self.handle_game_status,
                "ROUND_START": self.handle_round_start,
                "TIME_WARNING": self.handle_time_warning,
                "FINAL_SCORES": self.handle_final_scores
            }

            handler = handlers.get(message_type)
            if handler:
                handler(data)
            else:
                print(f"Otrzymano nieznany typ wiadomości: {message_type}")

        except json.JSONDecodeError:
            print("Błąd parsowania JSON z serwera.")
            
        self.network_queue.task_done()

    #---------------do wersji org----------------------

    def handle_nick_accepted(self, data):
        session_id = data.get("session_id", "BRAK ID")
        self.dane_gry['session_id'] = session_id
        
        print(f"Nick dostępny i zaakceptowany. ID sesji: {session_id}")
        
        self.pokaz_ekran(Lobby)

    def handle_nick_rejected(self, data):

        reason = data.get("reason", "Nick jest zajęty") # drugi argument wartosc domyslna
        
        messagebox.showerror(
            "Niepoprawny nick", 
            f"Wybrany przez ciebie nick jest już zajęty."
        )
        
        try:   #znowu mozna kliknac
            self.ekrany['Log_in_window'].connect_button.config(state='normal')
        except KeyError:
            print("Nie można odblokować przycisku, ekran logowania niedostępny.")


    def handle_network_error(self, data): # poprawic ta funkcje !

        reason = data.get("reason", "Nieznany błąd sieci.")
        
        messagebox.showerror(
            "Błąd Połączenia", 
            f"Brak połączenia z serwerem."
        )
        self.on_closing()
        
        try: 
            self.ekrany['Log_in_window'].connect_button.config(state='normal')
        except KeyError:
            print("Nie można odblokować przycisku, ekran logowania niedostępny.")


    def handle_game_status(self, data):
        ekran_lobby = self.ekrany['Lobby']
        game_state = data.get("game_status")
        current_round = data.get("current_round", 0)

        #if game_state == "IN_ROUND":
         #   current_round = data.get("current_round", 0)
         #   if not getattr(self, 'round_start_received', False):
          #      return
        
        if game_state == "IN_ROUND" or game_state == "GAME_OVER":
            # Akcja: Zawsze zatrzymujemy licznik, jeśli gra wystartowała lub się skończyła
            ekran_lobby.is_joined = False
            ekran_lobby.stop_countdown() 
            ekran_lobby.cancel_idle_timer()
            ekran_lobby.is_countdown_active = False
            
        elif game_state == "LOBBY":

            if self.current_round_active is not None: # potencjalnie do zmiany
                self.current_round_active = None  #
                self.pokaz_ekran(Lobby) #

            if not getattr(ekran_lobby, "is_joined", False):
                ekran_lobby.send_lobby_choice("WANT_TO_PLAY")
                ekran_lobby.is_joined = True
            ekran_lobby.player_message_label.config(text="")
            waiting_status = data.get("waiting_status") 
            time_remaining = data.get("time_remaining")
            
            if waiting_status == "COUNTDOWN":
                ekran_lobby.is_countdown_active = True
                ekran_lobby.cancel_idle_timer()
                if time_remaining is not None:
                    try:
                        remaining = int(time_remaining)
                        # Uruchamiamy lokalny timer
                        ekran_lobby.start_countdown(remaining) 
                        ekran_lobby.game_status_label.config(
                            text=f"GOTOWOŚĆ: Czekamy na pozostałych graczy." )
                    except ValueError:
                        ekran_lobby.stop_countdown()
                        ekran_lobby.game_status_label.config(
                            text="GOTOWOŚĆ: Odliczanie do startu (Brak czasu)."
                        )
                else:
                    ekran_lobby.stop_countdown()
                    ekran_lobby.game_status_label.config(
                        text="GOTOWOŚĆ: Odliczanie do startu (Brak czasu)."
                    )

            elif waiting_status == "IDLE":
                ekran_lobby.is_countdown_active = False
                ekran_lobby.stop_countdown() 
                ekran_lobby.game_status_label.config(
                    text="POCZEKALNIA: Czekamy na minimum 2 graczy,\n aby rozpocząć grę."
                )
                if not ekran_lobby.idle_timeout_id:
                    ekran_lobby.start_idle_timer()

        ekran_lobby.show_buttons(game_state, current_round)
                
        if game_state == "IN_ROUND":
            #current_round = data.get("current_round", 0)
            ekran_lobby.game_status_label.config(
                text=f"GRA TRWA: Rozpoczęła się Runda {current_round}/5."
            )
            if current_round >= 5:
                ekran_lobby.player_message_label.config(
                    text="Trwa ostatnia runda. Musisz poczekać na nową grę.")
            else:
                ekran_lobby.player_message_label.config(
                    text="Możesz dołączyć do następnej rundy lub czekać na nową grę."
                )
        elif game_state == "GAME_OVER":
            ekran_lobby.game_status_label.config(
                text="ROZGRYWKA ZAKOŃCZONA"
            )
            ekran_lobby.player_message_label.config(
                text="Rozgrywka zakończona. Trwa wypisywanie wyników, za chwilę zostaniesz \nprzekierowany do poczekalni."
            )
        
        #ekran_lobby.show_buttons(game_state) 

        #if game_state == "IN_ROUND":
         #   ekran_lobby.player_message_label.config(
        #        text="Gra trwa. Możesz dołączyć do następnej rundy lub czekać na nową grę."
        #    )
        #elif game_state == "LOBBY":
           # ekran_lobby.player_message_label.config(
             #   text="Kliknij 'Dołącz do Nowej Gry', aby zgłosić gotowość."
           # )
        #if game_state == "GAME_OVER":
         #   ekran_lobby.player_message_label.config(
         #       text="Rozgrywka zakończona. Trwa wypisywanie wyników, za chwilę zostaniesz \nprzekierowany do poczekalni."
         #   )


    def handle_round_start(self, data):
        players_count = data.get("players_count", 0)

        # sprawdzenie liczby graczy przy starcie
        if players_count < 2:
            messagebox.showwarning(
                "Błąd startu", 
                "Niestety, w grze pozostało zbyt mało graczy. Gra zostanie zamknięta." #ewentualnie dodac obsluge nprzejsz
            )
            self.on_closing() 
            return

        round_num = data.get("current_round")
        letter = data.get("letter")
        points = data.get("current_points", 0)
        
        if self.current_round_active == round_num: # aby okno sie czaly czas nie otwieralo
            return 
        self.current_round_active = round_num
        #self.round_start_received = True

        self.ekrany['Lobby'].is_joined = False #reset flagi is_joined do wysylania want_to_play
        self.pokaz_ekran(Game_window)
        self.ekrany['Game_window'].start_round_gui(round_num, letter, points)
        
        print(f"[GUI] Runda {round_num} wystartowała z {players_count} graczami.")

    def handle_time_warning(self, data):

        if self.current_round_active is None: #ignorowanie time_warning gdy jest w trakcie gry
            print("dostalam time_qwarning ignoruje")
            return

        time_left = data.get("time_left", 15)
        if 'Game_window' in self.ekrany:
            self.ekrany['Game_window'].activate_time_warning(time_left)

    def handle_final_scores(self, data):
        self.ekrany['Lobby'].is_joined = False
        self.pokaz_ekran(Result_window)
        self.ekrany['Result_window'].show_results(data)

if __name__ == "__main__":
    app = App()
    app.mainloop()