#pragma once
#include <glad/glad.h>
#include <string>
#include <vector>
#include <cstdio>
#include <cstdint>

class VideoPlayer {
public:
    VideoPlayer() = default;
    ~VideoPlayer() { close(); }

    // Open MP4 file — extracts all frames via ffmpeg into memory
    bool open(const std::string& path);
    void close();

    // Playback control
    void play()  { playing_ = true; }
    void pause() { playing_ = false; }
    void stop()  { playing_ = false; frame_ = 0; }
    void setFrame(int f) { frame_ = (f >= 0 && f < frameCount()) ? f : 0; }
    void setFPS(float fps) { fps_ = fps; }

    // Update (call each ImGui frame) — advances playback timer
    void update(float deltaTime);

    // Get current frame as OpenGL texture
    GLuint texture() const { return tex_; }
    int width() const { return w_; }
    int height() const { return h_; }
    int frameCount() const { return (int)frames_.size(); }
    int currentFrame() const { return frame_; }
    bool isPlaying() const { return playing_; }
    bool isLoaded() const { return !frames_.empty(); }
    const std::string& path() const { return path_; }

private:
    std::string path_;
    int w_ = 0, h_ = 0;
    std::vector<std::vector<uint8_t>> frames_;  // raw RGB per frame
    GLuint tex_ = 0;
    int frame_ = 0;
    int lastUploaded_ = -1;
    bool playing_ = false;
    float fps_ = 24.0f;
    float timer_ = 0.0f;

    void uploadFrame(int idx);
    bool probeVideo(const std::string& path, int& w, int& h, int& nframes, float& fps);
};
