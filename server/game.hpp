#pragma once
#include <vector>
#include <memory>
#include <string>
#include "client.hpp"
#include <map>

enum class GameState {
    LOBBY,
    COUNTDOWN,
    IN_ROUND,
    ROUND_SCORING,
    GAME_OVER
};



class Game {
private:
    GameState state;
    int countdown;
    int current_round;
    char current_letter;
    int round_time_remaining;
    bool round_started;
    bool time_warning_sent;

    std::vector<std::shared_ptr<client>> players;


    struct RoundSubmission {
    std::shared_ptr<client> player;
    std::map<std::string, std::string> answers;
    };

    std::vector<RoundSubmission> submissions;

public:
    Game();
    public:
    void setState(GameState newState) { state = newState; }
    GameState getState() const { return state; }

    void addPlayer(std::shared_ptr<client> p);
    void removePlayer(int socket);
    void startRound();
    void resetGame();

    bool tick(); // 

    std::string gameStatusJson(std::shared_ptr<client> p) const;
    std::string roundStartJson(std::shared_ptr<client> p) const;

    bool shouldStartRound() const;
    bool shouldSendTimeWarning();
    void submitAnswers(std::shared_ptr<client> player, const std::string& json_msg);
    void scoreRound();
    int game_over_timer;



};
