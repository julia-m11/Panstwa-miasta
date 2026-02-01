#pragma once

#include <map>
#include <vector>
#include <string>
#include <poll.h>
#include "client.hpp"
#include "game.hpp"

class Server {
public:
    explicit Server(int port);
    ~Server();

    void run();

private:
    int listen_fd;
    std::vector<pollfd> fds;

    std::map<int, std::shared_ptr<client>> clients;
    std::map<std::string, std::shared_ptr<client>> nicks;
 

    void setup_socket(int port);
    void accept_client();
    void handle_client(size_t index);
    void disconnect_client(int fd);

    void handle_message(std::shared_ptr<client> client, const std::string& msg);

    void handle_connecting(std::shared_ptr<client> client, const std::string& nick);

    void broadcast_game_status();
    void broadcast_round_start_if_needed();


    Game game;
};