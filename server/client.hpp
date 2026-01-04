#pragma once
#include <string>
#include <sys/socket.h>

enum class JoinIntent {
    NONE,
    NEXT_ROUND,
    NEXT_GAME
};

class client {
private:
    std::string nick;
    int sockDes;
    int points;
    int session_id;
    

public:
    bool nick_accepted;
    JoinIntent join_intent = JoinIntent::NONE;

    explicit client(int sock)
        : nick(""),
          sockDes(sock),
          points(0),
          session_id(sock),
          nick_accepted(false) {}

    const std::string& getNick() const {
        return nick;
    }

    void setNick(const std::string& n) {
        nick = n;
    }

    int getSocket() const {
        return sockDes;
    }

    int getSessionId() const {
        return session_id;
    }

    int getPoints() const {
        return points;
    }

    void addPoints(int p) {
        points += p;
    }

    void resetPoints() {
        points = 0;
    }

    int sendMessage(const std::string& msg) {
        std::string m = msg;
        if (m.empty() || m.back() != '\n')
            m += '\n';

        return send(sockDes, m.c_str(), m.size(), 0);
    }


};