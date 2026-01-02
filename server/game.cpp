#include "game.hpp"
#include <algorithm>
#include <cstdlib>
#include <ctime>
#include <sstream>
#include <map>


/*
{"type":"connecting_with_server","nick":"Tester1"}
{"type":"ROUND_END_ANSWERS","answers":{"państwo":"Polska","miasto":"Poznan","roślina":"Piwonia","zwierzę":"Papuga","rzecz":"Piłka"}}
{"type":"ROUND_END_ANSWERS","answers":{"państwo":"Polska","miasto":"Poznan","roślina":"","zwierzę":"Papuga","rzecz":"Piłka"}}
*/


Game::Game()
    : state(GameState::LOBBY),
      countdown(45),
      current_round(0),
      current_letter('A'),
      game_over_timer(0),  
      round_time_remaining(0),
      time_warning_sent(false)
{
    std::srand(std::time(nullptr));
}


void Game::addPlayer(std::shared_ptr<client> p) {
    players.push_back(p);

    if (players.size() >= 2 && state == GameState::LOBBY) {
        state = GameState::COUNTDOWN;
        countdown = 45;
    }
}

void Game::removePlayer(int socket) {
    players.erase(
        std::remove_if(players.begin(), players.end(),
            [socket](const std::shared_ptr<client>& p) {
                return p->getSocket() == socket;
            }),
        players.end()
    );

    if (players.size() < 2) {
        state = GameState::LOBBY;
        countdown = 10;
    }
}

bool Game::shouldStartRound() const {
    return state == GameState::IN_ROUND;
}

void Game::submitAnswers(std::shared_ptr<client> player, const std::string& msg) {
    if (state != GameState::IN_ROUND) return;


    auto it = std::find_if(submissions.begin(), submissions.end(),
        [&player](const RoundSubmission& s){ return s.player == player; });

    if (it != submissions.end()) return; 

    RoundSubmission sub;
    sub.player = player;

    for (const auto& cat : {"państwo","miasto","roślina","zwierzę","rzecz"}) {
        sub.answers[cat] = "";
    }


    size_t pos = 0;
    for (const auto& cat : {"państwo","miasto","roślina","zwierzę","rzecz"}) {
        std::string search = std::string("\"") + cat + "\":\"";
        pos = msg.find(search);
        if (pos != std::string::npos) {
            pos += search.size();
            size_t end = msg.find("\"", pos);
            if (end != std::string::npos) {
                sub.answers[cat] = msg.substr(pos, end - pos);
            }
        }
    }

    submissions.push_back(sub);


    if (!time_warning_sent && round_time_remaining > 10) {
        round_time_remaining = 10;
    }

    if (submissions.size() == players.size()) {
        state = GameState::ROUND_SCORING;
    }
}


void Game::scoreRound() {
    for (auto& sub : submissions) {
    int points = 0;
    for (const auto& cat : {"państwo","miasto","roślina","zwierzę","rzecz"}) {
        auto it = sub.answers.find(cat);
        std::string ans = (it != sub.answers.end()) ? it->second : "";

        if (ans.empty()) continue; 

        int count = 0;
        std::string ans_lower = ans;
        std::transform(ans_lower.begin(), ans_lower.end(), ans_lower.begin(), ::tolower);

        for (auto& other : submissions) {
            auto it2 = other.answers.find(cat);
            std::string other_ans = (it2 != other.answers.end()) ? it2->second : "";
            std::transform(other_ans.begin(), other_ans.end(), other_ans.begin(), ::tolower);
            if (other_ans == ans_lower) count++;
        }

        points += (count > 1) ? 10 : 15;
    }
    sub.player->addPoints(points);
}



    submissions.clear();

    if (current_round >= 5) {
        state = GameState::GAME_OVER;
        game_over_timer = 15;
    } else {
        state = GameState::COUNTDOWN;
        countdown = 10;
    }
}





bool Game::shouldSendTimeWarning() {
    if (state != GameState::IN_ROUND)
        return false;

    if (!time_warning_sent && round_time_remaining == 10) {
        time_warning_sent = true;
        return true;
    }
    return false;
}


bool Game::tick() {
    switch (state) {
        case GameState::COUNTDOWN:
            countdown--;
            if (countdown <= 0) {
                startRound();
                return true;
            }
            return true;

        case GameState::IN_ROUND:
            round_time_remaining--;
            if (round_time_remaining <= 0) {
                for (auto& p : players) {
                    auto it = std::find_if(submissions.begin(), submissions.end(),
                        [&p](const RoundSubmission& s){ return s.player == p; });

                    if (it == submissions.end()) {
                        RoundSubmission empty;
                        empty.player = p;
                        empty.answers = { {"państwo",""}, {"miasto",""}, {"roślina",""}, {"zwierzę",""}, {"rzecz",""} };
                        submissions.push_back(empty);
                    } else {
                        for (const auto& cat : {"państwo","miasto","roślina","zwierzę","rzecz"}) {
                            if (it->answers.find(cat) == it->answers.end())
                                it->answers[cat] = "";
                        }
                    }
                }

                state = GameState::ROUND_SCORING;
                return true;
            }
            return true;

        case GameState::ROUND_SCORING:
            scoreRound();
            return true;

        case GameState::GAME_OVER:
            game_over_timer--;
            if (game_over_timer <= 0) {
                resetGame();
                return true;
            }
            return true;

        default:
            return false;
    }
}




void Game::startRound() {
    state = GameState::IN_ROUND;
    current_round++;
    current_letter = 'A'+(std::rand() % 26);
    round_time_remaining = 180;
    time_warning_sent = false;
    submissions.clear();
}

void Game::resetGame() {
    state = GameState::LOBBY;
    countdown = 45;
    current_round = 0;
    submissions.clear();

    for (auto& p : players) {
        p->resetPoints();
    }
}



std::string Game::gameStatusJson(std::shared_ptr<client>) const {
    std::ostringstream o;

    if (state == GameState::LOBBY) {
        o << R"({"type":"GAME_STATUS","game_status":"LOBBY","waiting_status":"IDLE"})";
    }
    else if (state == GameState::COUNTDOWN) {
        o << R"({"type":"GAME_STATUS","game_status":"LOBBY","waiting_status":"COUNTDOWN","time_remaining":)"
          << countdown << "}";
    }
    else if (state == GameState::IN_ROUND) {
        o << R"({"type":"GAME_STATUS","game_status":"IN_ROUND","current_round":)"
          << current_round << "}";
    }

    o << "\n";
    return o.str();
}

std::string Game::roundStartJson(std::shared_ptr<client> p) const {
    std::ostringstream o;
    o << R"({"type":"ROUND_START","current_round":)"
      << current_round
      << R"(,"letter":")" << current_letter
      << R"(","current_points":)" << p->getPoints()
      << R"(,"players_count":)" << players.size()
      << "}";

    o << "\n";
    return o.str();
}
