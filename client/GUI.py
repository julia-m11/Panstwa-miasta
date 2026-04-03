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
        
        BG_COLOR = "#2C3E50" 
        ACCENT_COLOR = "#3498DB" 
        TEXT_COLOR = "#ECF0F1" 
        
        self.config(bg=BG_COLOR) 
        style = ttk.Style()
        style.configure("TLabel", background=BG_COLOR, foreground=TEXT_COLOR)
        
        title = tk.Label(
            self, 
            text="Państwa - Miasta", 
            font=("Helvetica", 28, "bold"), 
            bg=BG_COLOR, 
            fg=ACCENT_COLOR
        )
        title.pack(pady=(70, 10))
        form_container = tk.Frame(self, bg=BG_COLOR)
        form_container.pack(expand=True)

        self.create_field(form_container, "Nick:", "pole_nick")
        self.create_field(form_container, "Adres IP serwera:", "pole_ip")
        self.create_field(form_container, "Port serwera:", "pole_port")

        self.connect_button = tk.Button(
            self, 
            text="POŁĄCZ",
            font=("Helvetica", 12, "bold"),
            bg="#27AE60", 
            fg="white",
            activebackground="#2ECC71",
            activeforeground="white",
            relief="flat",
            width=20,
            height=2,
            cursor="hand2",
            command=self.connect_and_save
        )
        self.connect_button.pack(pady=(10, 100))

    def create_field(self, parent, label_text, attr_name):
        lbl = tk.Label(parent, text=label_text, font=("Helvetica", 9, "bold"), bg="#2C3E50", fg="#BDC3C7")
        lbl.pack(anchor="w", padx=20)
        
        entry = tk.Entry(
            parent, 
            width=30, 
            font=("Helvetica", 11), 
            bg="#34495E", 
            fg="white", 
            insertbackground="white", 
            relief="flat", 
            borderwidth=10
        )
        entry.pack(padx=20, pady=(5, 15))
        setattr(self, attr_name, entry)
        
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
            port_int = int(port_serwera)
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

        threading.Thread( 
            target=self.initiate_connection_and_login, 
            args=(nick, ip_serwera, port_int), 
            daemon=True
        ).start()

    def initiate_connection_and_login(self, nick, ip_serwera, port_serwera_int):
            
        self.kontroler.nawiaz_polaczenie_z_serwerem(ip_serwera, port_serwera_int)
    
        if self.kontroler.socket_polaczenia:
            sock = self.kontroler.socket_polaczenia
            
            dane_do_wyslania = {
                "type": "connecting_with_server", "nick": nick}
            network_manager.send_json(sock, dane_do_wyslania) 
            
            try:
                first_json_response = network_manager.receive_first_message_blocking(sock)
                
                if first_json_response:
                    self.kontroler.network_queue.put(first_json_response)
                    data = json.loads(first_json_response)
                    if data.get("type") == "nick_accepted":
                        self.kontroler.start_receiving_data() 
                    
                else: 
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
    
        BG_COLOR = "#2C3E50"      
        ACCENT_COLOR = "#3498DB"  
        TEXT_COLOR = "#ECF0F1"    
        RED_COLOR = "#E74C3C"     
        
        self.config(bg=BG_COLOR)
        self.is_joined = False

        self.countdown_id = None    
        self.remaining_time = 0     
        self.countdown_active = False  

        self.idle_timeout_id = None 
        self.IDLE_TIMEOUT_MS = 120000 
        self.is_countdown_active = False

        self.game_status_label = tk.Label(
            self, text="OCZEKIWANIE NA SERWER...", 
            font=("Helvetica", 22, "bold"), 
            bg=BG_COLOR, 
            fg=ACCENT_COLOR
        )
        self.game_status_label.pack(pady=(50, 10))

        self.player_message_label = tk.Label(
            self, text="", 
            font=("Helvetica", 13), 
            bg=BG_COLOR, 
            fg=TEXT_COLOR
        )
        self.player_message_label.pack(pady=(5, 5))

        self.countdown_label = tk.Label(
            self, text="", 
            font=("Helvetica", 32, "bold"), 
            bg=BG_COLOR, 
            fg=RED_COLOR
        )
        self.countdown_label.pack(pady=(20, 20))

        self.buttons_frame = tk.Frame(self, bg=BG_COLOR)
            
        self.btn_join_next_round = tk.Button(
            self.buttons_frame, 
            text="DOŁĄCZ DO KOLEJNEJ RUNDY",
            font=("Helvetica", 11, "bold"),
            bg="#27AE60", fg="white",
            activebackground="#2ECC71", activeforeground="white",
            relief="flat", width=30, height=2, cursor="hand2",
            command=lambda: self.send_lobby_choice("WANT_TO_PLAY_IN_NEXT_ROUND")
        )
        self.btn_join_next_round.pack(pady=10)
        
        self.btn_queue = tk.Button(
            self.buttons_frame, 
            text="CZEKAJ NA NOWĄ GRĘ",
            font=("Helvetica", 11, "bold"),
            bg="#2980B9", fg="white",
            activebackground="#3498DB", activeforeground="white",
            relief="flat", width=30, height=2, cursor="hand2",
            command=lambda: self.send_lobby_choice("WANT_TO_QUEUE")
        )
        self.btn_queue.pack(pady=10)

        self.hide_buttons() 

    def start_idle_timer(self):
        self.cancel_idle_timer()
        self.idle_timeout_id = self.after(self.IDLE_TIMEOUT_MS, self.force_quit_on_timeout) 

    def cancel_idle_timer(self):
        if self.idle_timeout_id:
            self.after_cancel(self.idle_timeout_id)
            self.idle_timeout_id = None 

    def force_quit_on_timeout(self): 
        self.idle_timeout_id = None 
        messagebox.showinfo(
            "Brak Graczy", 
            "Niestety, nikt nie dołączył do Lobby w ciągu 2 minut. Aplikacja zostanie zamknięta."
        )
        self.kontroler.on_closing() 
        
    def start_countdown(self, seconds):
        if self.countdown_id:
            self.after_cancel(self.countdown_id) 
            
        self.remaining_time = seconds
        self.countdown_active = True
        self.countdown_label.config(text=f"START GRY ZA: {self.remaining_time}s")
        self.countdown_label.pack(pady=10)
        
        self.update_countdown_gui()

    def update_countdown_gui(self):
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
        self.btn_join_next_round.grid_forget()
        self.btn_queue.grid_forget()
        
    def show_buttons(self, mode, current_round=0): 
        self.hide_buttons() 
        self.buttons_frame.pack_forget()
        
        if mode == 'GAME_OVER':
            return  

        if mode == 'IN_ROUND':
            self.buttons_frame.pack(pady=30)

            if current_round < 5:
                self.btn_join_next_round.grid(row=0, column=0, padx=10)
                self.btn_join_next_round.config(state='normal')

            self.btn_queue.grid(row=0, column=1, padx=10)
            self.btn_queue.config(state='normal')
        
        elif mode == 'LOBBY':
            # wysyłanie WANT_TO_PLAY 
            pass
            
    def send_lobby_choice(self, choice_type):
        self.kontroler.wyslij_wiadomosc_do_serwera({"type": choice_type})
        
        self.btn_queue.config(state='disabled')
        self.btn_join_next_round.config(state='disabled')

        if choice_type == "WANT_TO_PLAY":
        
            if not self.is_countdown_active:
                self.start_idle_timer()
            else:
                self.cancel_idle_timer()

    def reset_ui_lobby(self):
        self.countdown_label.pack_forget()
        self.countdown_label.config(text="")

# -------------------------------- okno gry -------------------------------------------------

class Game_window(tk.Frame):
    def __init__(self, parent, kontroler):
        tk.Frame.__init__(self, parent)
        self.kontroler = kontroler
        
        BG_COLOR = "#2C3E50"      
        CARD_COLOR = "#34495E"   
        ACCENT_COLOR = "#3498DB"  
        TEXT_COLOR = "#ECF0F1"    
        GOLD_COLOR = "#F1C40F"    
        
        self.config(bg=BG_COLOR)

    
        self.info_frame = tk.Frame(self, bg="#1A252F", height=60) # Ciemniejszy pasek na górze
        self.info_frame.pack(fill="x", side="top")

        self.round_label = tk.Label(
            self.info_frame, text="RUNDA: 1/5", 
            font=("Helvetica", 11, "bold"), bg="#1A252F", fg="#BDC3C7"
        )
        self.round_label.pack(side="left", padx=30, pady=15)

    
        self.letter_label = tk.Label(
            self.info_frame, text="LITERA: -", 
            font=("Helvetica", 24, "bold"), bg="#1A252F", fg=ACCENT_COLOR
        )
        self.letter_label.pack(side="left", expand=True)

        self.points_label = tk.Label(
            self.info_frame, text="PUNKTY: 0", 
            font=("Helvetica", 11, "bold"), bg="#1A252F", fg=GOLD_COLOR
        )
        self.points_label.pack(side="right", padx=30, pady=15)


        self.table_frame = tk.Frame(self, bg=BG_COLOR)
        self.table_frame.pack(pady=50)

        self.kategorie = ["Państwo", "Miasto", "Roślina", "Zwierzę", "Rzecz"]
        self.entries = {}


        for i, kat in enumerate(self.kategorie):
            # Kontener na każdą kolumnę (etykieta + pole)
            col_frame = tk.Frame(self.table_frame, bg=BG_COLOR)
            col_frame.grid(row=0, column=i, padx=10, pady=5)

            lbl = tk.Label(
                col_frame, text=kat.upper(), 
                font=("Helvetica", 9, "bold"), bg=BG_COLOR, fg="#95A5A6"
            )
            lbl.pack(pady=(0, 5))
            
            ent = tk.Entry(
                col_frame, width=16, font=("Helvetica", 12), 
                bg=CARD_COLOR, fg="white", insertbackground="white",
                relief="flat", borderwidth=8
            )
            ent.pack()
            self.entries[kat.lower()] = ent

    
        self.btn_stop = tk.Button(
            self, text="ZATWIERDŹ ODPOWIEDZI", 
            font=("Helvetica", 12, "bold"),
            bg="#27AE60", fg="white",
            activebackground="#2ECC71", activeforeground="white",
            relief="flat", width=25, height=2, cursor="hand2",
            command=lambda: self.send_answers(triggered_by_user=True)
        )
        self.btn_stop.pack(pady=30)

        self.warning_label = tk.Label(
            self, text="", font=("Helvetica", 12, "italic"), 
            fg="#2ECC71", bg=BG_COLOR
        )
        self.warning_label.pack(pady=5)
        
        self.auto_send_timer_id = None
        self.answers_sent = False 

    def start_round_gui(self, round_num, letter, points):
        self.answers_sent = False
        self.round_label.config(text=f"Runda: {round_num}/5")
        self.letter_label.config(text=f"LITERA: {letter}")
        self.points_label.config(text=f"Twoje punkty: {points}")
        
        for entry in self.entries.values():
            entry.config(state='normal')
            entry.delete(0, tk.END)
        self.btn_stop.config(state='normal')

        self.warning_label.config(text="") 
        if self.auto_send_timer_id:
            self.after_cancel(self.auto_send_timer_id)
            self.auto_send_timer_id = None

    def send_answers(self, triggered_by_user=False):
        if self.answers_sent:
            return 
        
        self.answers_sent = True

        self.btn_stop.config(state='disabled')
        for entry in self.entries.values():
            entry.config(state='disabled')

        if self.auto_send_timer_id:
            self.after_cancel(self.auto_send_timer_id)
            self.auto_send_timer_id = None

        odpowiedzi = {kat: ent.get() for kat, ent in self.entries.items()}
        self.kontroler.wyslij_wiadomosc_do_serwera({
            "type": "ROUND_END_ANSWERS",
            "answers": odpowiedzi
        })
        
        if triggered_by_user: 
            self.warning_label.config(
                text="Odpowiedzi wysłane. Czekanie na innych...",
                fg="green"
            )
        else:
            self.warning_label.config(
                text="Czas minął. Odpowiedzi wysłane automatycznie.",
                fg="green"
            )

    def activate_time_warning(self, seconds):
        if self.answers_sent:
            return 
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
            self.send_answers(triggered_by_user=False) 

# ------------------------------okno wynikow---------------------------------------------

class Result_window(tk.Frame):
    def __init__(self, parent, kontroler):
        tk.Frame.__init__(self, parent)
        self.kontroler = kontroler
        self.quit_timer_id = None
        
        BG_COLOR = "#2C3E50"
        CARD_COLOR = "#34495E"
        ACCENT_COLOR = "#3498DB"  
        GOLD_COLOR = "#F1C40F"    
        TEXT_COLOR = "#ECF0F1"
        
        self.config(bg=BG_COLOR)

        tk.Label(
            self, text="PODSUMOWANIE ROZGRYWKI", 
            font=("Helvetica", 26, "bold"), bg=BG_COLOR, fg=TEXT_COLOR
        ).pack(pady=(50, 10))

        self.personal_result_label = tk.Label(
            self, text="", 
            font=("Helvetica", 18, "bold"), bg=BG_COLOR, fg=ACCENT_COLOR
        )
        self.personal_result_label.pack(pady=10)

        tk.Label(
            self, text="RANKING NAJLEPSZYCH:", 
            font=("Helvetica", 12, "bold"), bg=BG_COLOR, fg="#95A5A6"
        ).pack(pady=(30, 5))

        self.ranking_label = tk.Label(
            self, text="", 
            font=("Consolas", 14), 
            bg=CARD_COLOR, fg=GOLD_COLOR,
            relief="flat", width=45, height=6,
            padx=20, pady=10
        )
        self.ranking_label.pack(pady=10)

        btn_frame = tk.Frame(self, bg=BG_COLOR)
        btn_frame.pack(pady=40)

        self.btn_join_new = tk.Button(
            btn_frame, 
            text="NOWA GRA", 
            font=("Helvetica", 11, "bold"),
            bg="#27AE60", fg="white",
            activebackground="#2ECC71", activeforeground="white",
            relief="flat", width=18, height=2, cursor="hand2",
            command=self.return_to_lobby
        )
        self.btn_join_new.grid(row=0, column=0, padx=15)

        self.btn_quit = tk.Button(
            btn_frame, 
            text="WYJDŹ", 
            font=("Helvetica", 11, "bold"),
            bg="#E74C3C", fg="white",
            activebackground="#C0392B", activeforeground="white",
            relief="flat", width=18, height=2, cursor="hand2",
            command=self.kontroler.on_closing
        )
        self.btn_quit.grid(row=0, column=1, padx=15)

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

    def start_return_timer(self, seconds):
        if self.quit_timer_id:
            self.after_cancel(self.quit_timer_id)
            
        if seconds > 0:
            self.timer_label.config(text=f"Powrót do poczekalni za: {seconds} s...")
            self.quit_timer_id = self.after(1000, lambda: self.start_return_timer(seconds - 1))
        else:
            print("Czas wyświetlania wyników minął")
            self.return_to_lobby()

    def return_to_lobby(self):
        # wywoła REQUEST_GAME_INFO 
        self.kontroler.pokaz_ekran(Lobby)
    
# ------------------------------glowne okno----------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Państwa-miasta")
        self.geometry("1000x600")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.receiver_thread = None

        self.network_queue = Queue() 
        self.socket_polaczenia = None 
        self.sprawdz_kolejke_sieciowa() 
        self.current_round_active = None
        
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

    def start_receiving_data(self): 
        if self.socket_polaczenia and not self.receiver_thread:
            self.receiver_thread = ReceiverThread( 
                sock=self.socket_polaczenia,
                queue=self.network_queue,
                controller=self
            )
            self.receiver_thread.start() 

    def pokaz_ekran(self, klasa_ekranu):
        nazwa = klasa_ekranu.__name__
        self.aktualna_nazwa_ekranu = nazwa
        frame = self.ekrany[nazwa]

        if klasa_ekranu == Lobby:
            frame.reset_ui_lobby()
            frame.show_lobby() 

        frame.tkraise()
        
    def on_closing(self): 
        if self.socket_polaczenia:
            try:
                self.socket_polaczenia.close()
                print("Połączenie sieciowe zamknięte.")
            except Exception as e:
                print(f"Błąd przy zamykaniu gniazda: {e}")
        self.destroy()


    def wyslij_wiadomosc_do_serwera(self, dane):
        #print(f"Wysylam wiadomosc - {dane}")
        if self.socket_polaczenia:
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
            print(f"Błąd podczas sprawdzania kolejki: {e}") 

        self.after(100, self.sprawdz_kolejke_sieciowa)

    def obsluz_odpowiedz_serwera(self, odpowiedz_json_string):
    
        try:
            data = json.loads(odpowiedz_json_string)
            #print(f"dostalam wiadomosc - {data}")
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

    #------------------handlery----------------------

    def handle_nick_accepted(self, data):
        session_id = data.get("session_id", "BRAK ID")
        self.dane_gry['session_id'] = session_id
        self.pokaz_ekran(Lobby)

    def handle_nick_rejected(self, data):

        reason = data.get("reason", "Nick jest zajęty") 
        
        messagebox.showerror(
            "Niepoprawny nick", 
            f"Wybrany przez ciebie nick jest już zajęty."
        )
        
        try:   
            self.ekrany['Log_in_window'].connect_button.config(state='normal')
        except KeyError:
            print("Nie można odblokować przycisku, ekran logowania niedostępny.")


    def handle_network_error(self, data):

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

        if game_state == "IN_ROUND" or game_state == "GAME_OVER":
            ekran_lobby.is_joined = False
            ekran_lobby.stop_countdown() 
            ekran_lobby.cancel_idle_timer()
            ekran_lobby.is_countdown_active = False
            
        elif game_state == "LOBBY":
            if getattr(self, 'aktualna_nazwa_ekranu', '') == 'Result_window':
                return

            if self.current_round_active is not None: 
                self.current_round_active = None  
                self.pokaz_ekran(Lobby) 

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

    def handle_round_start(self, data):
        players_count = data.get("players_count", 0)

        round_num = data.get("current_round")
        letter = data.get("letter")
        points = data.get("current_points", 0)
        
        if self.current_round_active == round_num: 
            return 
        self.current_round_active = round_num

        self.ekrany['Lobby'].is_joined = False 
        self.pokaz_ekran(Game_window)
        self.ekrany['Game_window'].start_round_gui(round_num, letter, points)

    def handle_time_warning(self, data):

        if self.current_round_active is None:
            return

        time_left = data.get("time_remaining", 10)
        if 'Game_window' in self.ekrany:
            self.ekrany['Game_window'].activate_time_warning(time_left)

    def handle_final_scores(self, data):
        self.ekrany['Lobby'].is_joined = False
        self.pokaz_ekran(Result_window)
        self.ekrany['Result_window'].show_results(data)

if __name__ == "__main__":
    app = App()
    app.mainloop()