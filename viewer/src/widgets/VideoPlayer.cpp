#include "widgets/VideoPlayer.hpp"
#include <iostream>
#include <sstream>
#include <cstring>
#include <array>

// Run command and capture stdout
static std::string execCmd(const std::string& cmd) {
    std::array<char, 256> buf;
    std::string result;
    FILE* pipe = popen(cmd.c_str(), "r");
    if (!pipe) return "";
    while (fgets(buf.data(), (int)buf.size(), pipe)) {
        result += buf.data();
    }
    pclose(pipe);
    return result;
}

bool VideoPlayer::probeVideo(const std::string& path, int& w, int& h, int& nframes, float& fps) {
    // Use ffprobe to get video dimensions and frame count
    std::string cmd = "ffprobe -v error -select_streams v:0 "
                      "-show_entries stream=width,height,r_frame_rate,nb_frames "
                      "-of csv=p=0 \"" + path + "\" 2>/dev/null";
    std::string out = execCmd(cmd);
    if (out.empty()) return false;

    // Parse: width,height,fps_num/fps_den,nb_frames
    // e.g.: 1280,720,24/1,22
    std::istringstream ss(out);
    std::string token;
    std::vector<std::string> tokens;
    while (std::getline(ss, token, ',')) tokens.push_back(token);

    if (tokens.size() < 3) return false;
    w = std::stoi(tokens[0]);
    h = std::stoi(tokens[1]);

    // Parse fps fraction
    size_t slash = tokens[2].find('/');
    if (slash != std::string::npos) {
        float num = std::stof(tokens[2].substr(0, slash));
        float den = std::stof(tokens[2].substr(slash + 1));
        fps = (den > 0) ? num / den : 24.0f;
    } else {
        fps = std::stof(tokens[2]);
    }

    // nb_frames might be N/A
    if (tokens.size() >= 4 && tokens[3].find_first_of("0123456789") != std::string::npos) {
        nframes = std::stoi(tokens[3]);
    } else {
        nframes = 0;  // unknown, will count from raw data
    }

    return (w > 0 && h > 0);
}

bool VideoPlayer::open(const std::string& path) {
    close();
    path_ = path;

    // Probe
    int nframes = 0;
    float fps = 24.0f;
    if (!probeVideo(path, w_, h_, nframes, fps)) {
        std::cerr << "[VideoPlayer] ffprobe failed for: " << path << "\n";
        return false;
    }
    fps_ = fps;

    std::cout << "[VideoPlayer] " << path << " → " << w_ << "x" << h_
              << " @ " << fps_ << "fps, ~" << nframes << " frames\n";

    // Decode all frames via ffmpeg pipe
    std::string cmd = "ffmpeg -v error -i \"" + path +
                      "\" -f rawvideo -pix_fmt rgb24 pipe:1 2>/dev/null";
    FILE* pipe = popen(cmd.c_str(), "r");
    if (!pipe) {
        std::cerr << "[VideoPlayer] ffmpeg pipe failed\n";
        return false;
    }

    size_t frameBytes = (size_t)w_ * h_ * 3;
    std::vector<uint8_t> buf(frameBytes);

    while (true) {
        size_t read = fread(buf.data(), 1, frameBytes, pipe);
        if (read < frameBytes) break;
        frames_.push_back(buf);
    }
    pclose(pipe);

    if (frames_.empty()) {
        std::cerr << "[VideoPlayer] No frames decoded\n";
        return false;
    }

    std::cout << "[VideoPlayer] Decoded " << frames_.size() << " frames\n";

    // Create OpenGL texture
    glGenTextures(1, &tex_);
    glBindTexture(GL_TEXTURE_2D, tex_);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, w_, h_, 0, GL_RGB, GL_UNSIGNED_BYTE, nullptr);

    // Upload first frame
    uploadFrame(0);

    return true;
}

void VideoPlayer::close() {
    if (tex_) { glDeleteTextures(1, &tex_); tex_ = 0; }
    frames_.clear();
    frame_ = 0;
    lastUploaded_ = -1;
    playing_ = false;
    w_ = h_ = 0;
}

void VideoPlayer::update(float deltaTime) {
    if (!playing_ || frames_.empty()) return;

    timer_ += deltaTime;
    float frameDur = 1.0f / fps_;
    if (timer_ >= frameDur) {
        timer_ -= frameDur;
        frame_++;
        if (frame_ >= (int)frames_.size()) {
            frame_ = 0;  // loop
        }
    }

    uploadFrame(frame_);
}

void VideoPlayer::uploadFrame(int idx) {
    if (idx == lastUploaded_ || idx < 0 || idx >= (int)frames_.size()) return;
    lastUploaded_ = idx;

    glBindTexture(GL_TEXTURE_2D, tex_);
    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w_, h_, GL_RGB, GL_UNSIGNED_BYTE, frames_[idx].data());
}
