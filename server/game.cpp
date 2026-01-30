#include "game.hpp"
#include <algorithm>
#include <cstdlib>
#include <ctime>
#include <sstream>
#include <map>

Game::Game()
    : state(GameState::LOBBY),
      countdown(45),
      current_round(0),
      current_letter('A'),
      game_over_timer(0),  
      round_time_remaining(0),
      time_warning_sent(false),
      round_start_pending(false),
      forced_round_end(false),
      scoring_pending(false),
      round_closing(false)
 
{
    std::srand(std::time(nullptr));
}

int Game::getCurrentRound() const {
    return current_round;
}


void Game::addPlayer(std::shared_ptr<client> p) {
    auto it = std::find(players.begin(), players.end(), p);
    if (it != players.end()) {
        return;
    }

    p->resetPoints(); 
    p->join_intent = JoinIntent::NONE;

    if (state == GameState::IN_ROUND || state == GameState::ROUND_SCORING) {
        queued_players.push_back(p);
        return;
    }
    players.push_back(p);

    if (players.size() >= 2 && state == GameState::LOBBY) {
        state = GameState::COUNTDOWN;
        countdown = 45;
    }
}

void Game::removePlayer(int socket) {
    auto it = std::find_if(players.begin(), players.end(),
        [socket](const std::shared_ptr<client>& p) {
            return p->getSocket() == socket;
        });
    if (it == players.end())
        return;
    auto removed = *it;
    players.erase(it);

    submissions.erase(
        std::remove_if(submissions.begin(), submissions.end(),
            [&](const RoundSubmission& s) {
                return s.player == removed;
            }),
        submissions.end()
    );

    if (state == GameState::IN_ROUND || state == GameState::ROUND_SCORING) {

        if (players.size() < 2) {
            submissions.clear();
            round_closing = false;
            scoring_pending = false;
            forced_round_end = false;
            round_start_pending = false;
            state = GameState::LOBBY;
            countdown = 45;
            current_round = 0;
            return;
        }
        if (submissions.size() == players.size()) {
            state = GameState::ROUND_SCORING;
            scoring_pending = true;
        }
    }

    if (players.size() < 2) {
        state = GameState::LOBBY;
        countdown = 45;
    }
}

bool Game::shouldStartRound() {
    if (round_start_pending) {
        round_start_pending = false;
        return true;
    }
    return false;
}

void Game::submitAnswers(std::shared_ptr<client> player, const std::string& msg) {
    if (state != GameState::IN_ROUND && !round_closing) return;
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
    bool first_submission = submissions.empty();
    submissions.push_back(sub);
    if (first_submission && players.size() > 1) {
        round_time_remaining = 15;
        time_warning_sent = false;
        forced_round_end = true;
    }
    if (submissions.size() == players.size()) {
        state = GameState::ROUND_SCORING;
        scoring_pending = true;
    }
}

static bool isValidWord(const std::string& s) {
    if (s.size() < 3)
        return false;

    for (unsigned char c : s) {
        if (!std::isalpha(c))
            return false;
    }
    return true;
}

void Game::scoreRound() {
    char lower_current = std::tolower(static_cast<unsigned char>(current_letter));
    for (auto& sub : submissions) {
        int points = 0;

        for (const auto& cat : {"państwo","miasto","roślina","zwierzę","rzecz"}) {
            auto it = sub.answers.find(cat);
            if (it == sub.answers.end())
                continue;

            std::string ans = it->second;
            if (!isValidWord(ans))
                continue;

            std::string ans_lower = ans;
            std::transform(ans_lower.begin(), ans_lower.end(), ans_lower.begin(), ::tolower);
            if (ans_lower[0] != lower_current)
                continue;
            int count = 0;
            for (auto& other : submissions) {
                auto it2 = other.answers.find(cat);
                if (it2 == other.answers.end())
                    continue;
                std::string other_ans = it2->second;
                if (!isValidWord(other_ans))
                    continue;
                std::transform(other_ans.begin(), other_ans.end(),
                               other_ans.begin(), ::tolower);
                if (other_ans == ans_lower)
                    count++;
            }
            points += (count > 1) ? 10 : 15;
        }
        sub.player->addPoints(points);
    }
    submissions.clear();
    state = GameState::COUNTDOWN;
    countdown = 7;   
}


bool Game::shouldSendTimeWarning() {
    if (state != GameState::IN_ROUND)
        return false;
    if (!time_warning_sent && round_time_remaining == 15) {
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
        return false;

    case GameState::IN_ROUND:
        round_time_remaining--;
        if (round_time_remaining <= 0 && !round_closing) {
            round_closing = true;
            return false;
        }
        if (round_closing || submissions.size() == players.size()) {
            state = GameState::ROUND_SCORING;
            scoring_pending = true;
            return true;
        }
        return false;

    case GameState::ROUND_SCORING:
        if (scoring_pending) {
            scoring_pending = false;
            scoreRound();
            return true;
        }
        return false;

    case GameState::GAME_OVER: {
        size_t ready = 0;
        for (auto& p : players) {
            if (p->join_intent == JoinIntent::NEXT_GAME)
                ready++;
        }

        if (ready >= 2) {
            resetGame();
            return true;
        }

        game_over_timer--;
        if (game_over_timer <= 0) {
            resetGame();
            return true;
        }
        return false;
    }

    default:
        return false;
    }
}

void Game::startRound() {
    if (!submissions.empty()) {
        scoreRound();
    }
    if (current_round >= 5) {
        state = GameState::GAME_OVER;
        game_over_timer = 20;
        return;
    }

    for (auto& p : next_round_players) {
        if (std::find(players.begin(), players.end(), p) == players.end()) {
            players.push_back(p);
        }
        p->join_intent = JoinIntent::NONE;
    }
    next_round_players.clear();
    state = GameState::IN_ROUND;
    current_round++;

    if (current_round == 1) {
        for (auto& p : players) {
            p->resetPoints();
        }
    }
    std::string allowed_letters = "ABCDEFGHIJKLMNOPRSTUWZ";

    std::vector<char> available;
    for (char c : allowed_letters) {
        if (std::find(used_letters.begin(), used_letters.end(), c) == used_letters.end()) {
            available.push_back(c);
        }
    }

    if (available.empty()) {
        used_letters.clear();
        for (char c : allowed_letters) {
            available.push_back(c);
        }
    }

    current_letter = available[std::rand() % available.size()];
    used_letters.push_back(current_letter);

    round_time_remaining = 180;
    time_warning_sent = false;
    submissions.clear();
    round_start_pending = true;
    forced_round_end = false;
    round_closing = false;
}

void Game::resetGame() {
    std::vector<std::shared_ptr<client>> still_playing;
    for (auto& p : players) {
        if (p->join_intent == JoinIntent::NEXT_GAME) {
            p->resetPoints();
            p->join_intent = JoinIntent::NONE;
            still_playing.push_back(p);
        }
    }
    for (auto& p : queued_players) {
        p->resetPoints();
        p->join_intent = JoinIntent::NONE;
        still_playing.push_back(p);
    }
    players = std::move(still_playing);
    queued_players.clear();
    next_round_players.clear();
    used_letters.clear();
    current_round = 0;
    countdown = 45;
    submissions.clear();
    forced_round_end = false;
    round_closing = false;
    scoring_pending = false;
    round_start_pending = false;
    time_warning_sent = false;
    if (players.size() >= 2) {
        state = GameState::COUNTDOWN;
    } else {
        state = GameState::LOBBY;
    }
}

void Game::addToNextRound(std::shared_ptr<client> p) {
    if (std::find(next_round_players.begin(), next_round_players.end(), p)
        == next_round_players.end()) {
        next_round_players.push_back(p);
    }
}

void Game::addToQueue(std::shared_ptr<client> p) {
    if (std::find(queued_players.begin(), queued_players.end(), p)
        == queued_players.end()) {
        queued_players.push_back(p);
    }
}

std::string Game::gameStatusJson(std::shared_ptr<client>) const {
    std::ostringstream o;

    if (state == GameState::IN_ROUND || state == GameState::ROUND_SCORING || (state == GameState::COUNTDOWN && current_round > 0)) {
        o << R"({"type":"GAME_STATUS","game_status":"IN_ROUND","current_round":)"
          << current_round << "}";
    }
    else if (state == GameState::LOBBY) {
        o << R"({"type":"GAME_STATUS","game_status":"LOBBY","waiting_status":"IDLE"})";
    }
    else if (state == GameState::COUNTDOWN) {
        o << R"({"type":"GAME_STATUS","game_status":"LOBBY","waiting_status":"COUNTDOWN","time_remaining":)"
          << countdown << "}";
    }
    else if (state == GameState::GAME_OVER) {
        o << R"({"type":"GAME_STATUS","game_status":"LOBBY","waiting_status":"IDLE"})";
    }
    return o.str();
}

std::string Game::roundStartJson(std::shared_ptr<client> p) {
    std::ostringstream o;
    o << R"({"type":"ROUND_START","current_round":)"
      << current_round
      << R"(,"letter":")" << current_letter
      << R"(","current_points":)" << p->getPoints()
      << R"(,"players_count":)" << players.size()
      << "}";
    return o.str();
}

std::string Game::finalScoresJson(std::shared_ptr<client> p) {
    std::vector<std::shared_ptr<client>> sorted = players;
    std::sort(sorted.begin(), sorted.end(),
        [](auto a, auto b) {
            return a->getPoints() > b->getPoints();
        });
    int place = 1;
    for (size_t i = 0; i < sorted.size(); ++i) {
        if (sorted[i] == p) {
            place = i + 1;
            break;
        }
    }
    std::ostringstream o;
    o << R"({"type":"FINAL_SCORES")";
    o << R"(,"your_place":)" << place;
    o << R"(,"total_points":)" << p->getPoints();
    o << R"(,"top_3":[)";
    for (size_t i = 0; i < sorted.size() && i < 3; ++i) {
        if (i > 0) o << ",";
        o << R"({"nick":")" << sorted[i]->getNick()
          << R"(","points":)" << sorted[i]->getPoints() << "}";
    }
    o << "]}";
    return o.str();
}

bool Game::wasPlayerInCurrentGame(std::shared_ptr<client> c) const {
    return std::find(players.begin(), players.end(), c) != players.end();
}
bool Game::tryStartLobbyCountdown() {
    if (state != GameState::LOBBY && state != GameState::GAME_OVER)
        return false;
    size_t ready = 0;
    for (auto& p : players) {
        if (p->join_intent == JoinIntent::NEXT_GAME)
            ready++;
    }
    ready += queued_players.size();
    if (ready >= 2) {
        //countdown = 45;
        //current_round = 0;
        //state = GameState::COUNTDOWN;
        resetGame();
        return true;
    }
    return false;
}