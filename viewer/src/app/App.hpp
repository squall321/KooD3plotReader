#pragma once
#include <string>

struct GLFWwindow;

class App {
public:
    bool init(int width, int height, const char* title);
    void run(const std::string& d3plotPath);
    void shutdown();

private:
    GLFWwindow* window_ = nullptr;
};
