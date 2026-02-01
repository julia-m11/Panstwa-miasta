#include "server.hpp"
#include "game.hpp"  
#include <iostream>
#include <unistd.h>
#include <arpa/inet.h>
#include <cstring>
#include <sstream>
#include <memory>

Server::Server(int port) {
    setup_socket(port);
}

Server::~Server() {
    for (auto& [fd, c] : clients) {
        close(fd);
    }
    close(listen_fd);
}

void Server::setup_socket(int port) {
    listen_fd = socket(AF_INET, SOCK_STREAM, 0);
    int opt = 1;
    if (setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0) {
        perror("Błąd setsockopt");
    }
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(port);
    bind(listen_fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
    listen(listen_fd, SOMAXCONN);
    fds.push_back({listen_fd, POLLIN, 0});
    std::cout << "Server listening on port " << port << std::endl;
}

void Server::broadcast_round_start_if_needed() {
    if (!game.shouldStartRound())
        return;
    for (auto& p : game.getPlayers()) {
        p->sendMessage(game.roundStartJson(p));
    }
}

void Server::run() {
    while (true) {
        poll(fds.data(), fds.size(), 1000);
        for (size_t i = 0; i < fds.size(); ++i) {
            if (fds[i].revents & POLLIN) {
                if (fds[i].fd == listen_fd) {
                    accept_client();
                } else {
                    handle_client(i);
                }
            }
        }
        GameState prev = game.getState();
        bool state_changed = game.tick();
        GameState now = game.getState();
        if (prev != GameState::GAME_OVER && now == GameState::GAME_OVER) {
        for (auto& [fd, c] : clients) {
            if (c->nick_accepted && game.wasPlayerInCurrentGame(c)) {
                c->sendMessage(game.finalScoresJson(c));
            }
        }
    }

    if (prev == GameState::GAME_OVER && now != GameState::GAME_OVER) {
        broadcast_game_status();
    }
        if (game.shouldSendTimeWarning()) {
            for (auto& p : game.getPlayers()) {
                p->sendMessage(
                    R"({"type":"TIME_WARNING","time_remaining":10})"
                );
            }
        }
        if (state_changed && prev != now) {
            broadcast_round_start_if_needed();
        }
    }
}

void Server::accept_client() {
    int fd = accept(listen_fd, nullptr, nullptr);
    fds.push_back({fd, POLLIN, 0});
    clients[fd] = std::make_shared<client>(fd);
    std::cout << "New client fd=" << fd << std::endl;
}

void Server::handle_client(size_t index) {
    int fd = fds[index].fd;
    char buf[1024];

    int r = recv(fd, buf, sizeof(buf) - 1, 0);
    if (r <= 0) {
        disconnect_client(fd);
        fds.erase(fds.begin() + index);
        return;
    }
    buf[r] = 0;
    std::string msg(buf);
    std::cout << "RX: " << msg;
    handle_message(clients[fd], msg);
}

void Server::disconnect_client(int fd) {
    std::shared_ptr<client> c = clients[fd];
    if (!c->getNick().empty()) {
        nicks.erase(c->getNick());
        game.removePlayer(c->getSocket());
    }
    close(fd);
    clients.erase(fd);
    broadcast_game_status();
}

static std::string extractType(const std::string& msg) {
    auto pos = msg.find("\"type\"");
    if (pos == std::string::npos) return "";
    pos = msg.find(":", pos);
    if (pos == std::string::npos) return "";

    pos++;
    while (pos < msg.size() && (msg[pos] == ' ' || msg[pos] == '"'))
        pos++;
    auto end = msg.find("\"", pos);
    if (end == std::string::npos) return "";
    return msg.substr(pos, end - pos);
}

void Server::handle_message(std::shared_ptr<client> client, const std::string& msg) {
    std::string type = extractType(msg);
    if (type == "connecting_with_server") {
        auto pos = msg.find("\"nick\":\"");
        if (pos == std::string::npos) return;

        std::string nick = msg.substr(pos + 8);
        if (auto end = nick.find("\""); end != std::string::npos) {
            nick.resize(end);
        }
        handle_connecting(client, nick);
        return;
    }
    if (type == "REQUEST_GAME_INFO") {
        client->sendMessage(game.gameStatusJson(client));
        return;
    }
    if (type == "ROUND_END_ANSWERS") {
        game.submitAnswers(client, msg);
        if (game.shouldSendTimeWarning()) {
            for (auto& [fd, c] : clients) {
                if (c->nick_accepted) {
                    c->sendMessage(
                        R"({"type":"TIME_WARNING","time_remaining":10})"
                    );
                }
            }
        }
        return;
    }
    if (type == "WANT_TO_PLAY") {
        GameState state = game.getState();

        if (state == GameState::IN_ROUND || state == GameState::COUNTDOWN || state == GameState::ROUND_SCORING) {
            client->sendMessage(game.gameStatusJson(client));
            return;
        }
        if (state == GameState::LOBBY || state == GameState::GAME_OVER) {
            client->join_intent = JoinIntent::NEXT_GAME;
            if (game.tryStartLobbyCountdown()) {
                broadcast_game_status();
            } else {
                client->sendMessage(game.gameStatusJson(client));
            }
            return;
        }
    }
    if (type == "WANT_TO_PLAY_IN_NEXT_ROUND") {
        client->join_intent = JoinIntent::NEXT_ROUND;
        game.addToNextRound(client);
        return;
    }
    if (type == "WANT_TO_QUEUE") {
        client->join_intent = JoinIntent::NEXT_GAME;
        game.addToQueue(client);
        return;
    }
}

void Server::handle_connecting(std::shared_ptr<client> c, const std::string& nick) {
    if (nicks.count(nick)) {
        c->sendMessage(R"({"type":"nick_rejected","reason":"Ten nick jest zajęty"})");
        return;
    }

    c->setNick(nick);
    c->nick_accepted = true;
    nicks[nick] = c;

    c->sendMessage(
        R"({"type":"nick_accepted","session_id":)"
        + std::to_string(c->getSessionId()) + "}"
    );

    GameState state = game.getState();
    int current_round = game.getCurrentRound();
    if (state == GameState::IN_ROUND || state == GameState::ROUND_SCORING || (state == GameState::COUNTDOWN && current_round > 0)) {
        std::ostringstream o;
        o << R"({"type":"GAME_STATUS","game_status":"IN_ROUND","current_round":)"
          << current_round << "}";
        c->sendMessage(o.str());
        std::cout << "Nick accepted during active game: " << nick << std::endl;
        return;
    }

    game.addPlayer(c);
    broadcast_game_status();
    std::cout << "Nick accepted: " << nick << std::endl;
}


void Server::broadcast_game_status() {
    GameState current_state = game.getState();
    for (auto& [fd, c] : clients) {
        if (!c->nick_accepted) continue;
        bool should_send = false;

        if (current_state == GameState::LOBBY) {
            should_send = true; 
        }
        
        else if (current_state == GameState::COUNTDOWN) {
            if (c->join_intent != JoinIntent::NONE) {
                should_send = true;
            }
        }
        
        else if (current_state == GameState::IN_ROUND || current_state == GameState::ROUND_SCORING) {
            if (game.wasPlayerInCurrentGame(c)) {
                should_send = true;
            }
        }
        
        else if (current_state == GameState::GAME_OVER) {
            should_send = true; 
        }

        if (should_send) {
            c->sendMessage(game.gameStatusJson(c));
        }
    }
}
