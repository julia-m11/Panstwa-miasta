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
    int game_over_timer;
    bool round_start_pending;
    bool forced_round_end;

    std::vector<std::shared_ptr<client>> players;
    std::vector<std::shared_ptr<client>> next_round_players;
    std::vector<std::shared_ptr<client>> queued_players; 

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

    bool tick(); 


    bool shouldStartRound();
    bool shouldSendTimeWarning();
    void submitAnswers(std::shared_ptr<client> player, const std::string& json_msg);
    void scoreRound();
    void addToNextRound(std::shared_ptr<client> p);
    void addToQueue(std::shared_ptr<client> p);
    const std::vector<std::shared_ptr<client>>& getPlayers() const {
        return players;
    }


    std::string gameStatusJson(std::shared_ptr<client> p) const;
    std::string roundStartJson(std::shared_ptr<client> p);
    std::string finalScoresJson(std::shared_ptr<client> p);

};