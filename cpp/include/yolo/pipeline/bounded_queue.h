#pragma once
#include <queue>
#include <mutex>
#include <condition_variable>
#include <optional>

namespace yolo {

template<typename T>
class BoundedQueue {
public:
    BoundedQueue(size_t max_size=8, const std::string& drop_policy="oldest")
        : max_size_(max_size), drop_policy_(drop_policy) {}

    void put(T item) {
        std::unique_lock<std::mutex> lock(mtx_);
        if (queue_.size() >= max_size_) {
            if (drop_policy_=="oldest") {
                queue_.pop();
            } else if (drop_policy_=="newest") {
                return;
            }
        }
        queue_.push(std::move(item));
        cv_.notify_one();
    }

    bool get(T& out, int timeout_ms=100) {
        std::unique_lock<std::mutex> lock(mtx_);
        if (queue_.empty()) {
            if (timeout_ms<=0) return false;
            cv_.wait_for(lock, std::chrono::milliseconds(timeout_ms), [this]{return !queue_.empty();});
            if (queue_.empty()) return false;
        }
        out = std::move(queue_.front());
        queue_.pop();
        return true;
    }

    bool empty() const { std::lock_guard<std::mutex> lock(mtx_); return queue_.empty(); }
    size_t size() const { std::lock_guard<std::mutex> lock(mtx_); return queue_.size(); }

private:
    mutable std::mutex mtx_;
    std::condition_variable cv_;
    std::queue<T> queue_;
    size_t max_size_;
    std::string drop_policy_;
};

}
