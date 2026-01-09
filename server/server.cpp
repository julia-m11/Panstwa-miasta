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
    setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(port);

    bind(listen_fd, (sockaddr*)&addr, sizeof(addr));
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
            if (c->nick_accepted) {
                c->sendMessage(game.finalScoresJson(c));
            }
        }
    }

        if (game.shouldSendTimeWarning()) {
            for (auto& p : game.getPlayers()) {
                p->sendMessage(
                    R"({"type":"TIME_WARNING","time_remaining":15})"
                );
            }

        }

        if (state_changed) {
            /*
            if (game.getState() != GameState::IN_ROUND) {
                broadcast_game_status();
            }
            */
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


void Server::handle_message(std::shared_ptr<client> client, const std::string& msg) {
    if (msg.find("connecting_with_server") != std::string::npos) {
        auto pos = msg.find("\"nick\":\"");
        if (pos == std::string::npos) return;

        std::string nick = msg.substr(pos + 8);
        nick = nick.substr(0, nick.find("\""));

        handle_connecting(client, nick);
    }
    else if (msg.find("REQUEST_GAME_INFO") != std::string::npos) {
        if (game.getState() == GameState::IN_ROUND || game.getState() == GameState::ROUND_SCORING || game.getState() == GameState::COUNTDOWN) {
            client->sendMessage(game.gameStatusJson(client));
        }
    }
    else if (msg.find("ROUND_END_ANSWERS") != std::string::npos) {
        game.submitAnswers(client, msg);
        
        if (game.shouldSendTimeWarning()) {
            for (auto& [fd, c] : clients) {
                if (c->nick_accepted) {
                    c->sendMessage(
                        R"({"type":"TIME_WARNING","time_remaining":15})"
                    );
                }
            }
        }
    }

    else if (msg.find("\"type\":\"WANT_TO_PLAY_IN_NEXT_ROUND\"") != std::string::npos) {
        client->join_intent = JoinIntent::NEXT_ROUND;
        game.addToNextRound(client);
    }

    else if (msg.find("\"type\":\"WANT_TO_QUEUE\"") != std::string::npos) {
        client->join_intent = JoinIntent::NEXT_GAME;
        game.addToQueue(client);
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

    c->sendMessage(R"({"type":"nick_accepted","session_id":)" 
                   + std::to_string(c->getSessionId()) + "}");


    game.addPlayer(c);
    if (game.getState() == GameState::IN_ROUND ||
        game.getState() == GameState::ROUND_SCORING) {
        c->sendMessage(game.gameStatusJson(c));
    }
    game.addPlayer(c);
    if (game.getState() != GameState::IN_ROUND &&
        game.getState() != GameState::ROUND_SCORING) {
        broadcast_game_status();
    }

    std::cout << "Nick accepted: " << nick << std::endl;
}




void Server::broadcast_game_status() {
    for (auto& [fd, c] : clients) {
        if (c->nick_accepted) {
            std::string json = game.gameStatusJson(c);
            if (!json.empty()) {
                c->sendMessage(json);
            }
        }
    }
}


void Server::send_json(int fd, const std::string& json) {
    send(fd, json.c_str(), json.size(), 0);
    std::cout << "TX: " << json;
}