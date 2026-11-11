#include "net/Channel.h"
#include "net/EventLoop.h"

namespace net {
void Channel::enableWriting()  { events_ |= 0x04; /*EPOLLOUT*/ loop_->updateChannel(this); }
void Channel::disableWriting() { events_ &= ~0x04; loop_->updateChannel(this); }
}  // namespace net
