package chanx

import (
	"testing"
	"time"
)

func TestUnbufferedSync(t *testing.T) {
	sendTime, ok := UnbufferedSync()
	if !ok {
		t.Error("无缓冲发送应完成")
	}
	if sendTime > 100*time.Millisecond {
		t.Errorf("有接收方等待时发送应近乎立即返回: %v", sendTime)
	}
}

func TestBufferedNoBlock(t *testing.T) {
	if drops := BufferedNoBlock(); drops != 0 {
		t.Errorf("缓冲应吸收 3 次发送: %d", drops)
	}
}

func TestClosedRead(t *testing.T) {
	zero, ok, drained := ClosedRead()
	if drained != 3 {
		t.Errorf("range 应读完 1+2: %d", drained)
	}
	if ok {
		t.Error("关闭且空后读取 ok 应为 false")
	}
	if zero != 0 {
		t.Errorf("关闭且空后读取零值应为 0: %d", zero)
	}
}

func TestSelectRandom(t *testing.T) {
	a, b := SelectRandom(200)
	if a == 0 || b == 0 {
		t.Errorf("select 应在两个就绪分支间随机（a=%d b=%d），不应固定选一边", a, b)
	}
	// 概率上各 ~50%；只断言"两边都被选过"，不断言具体比例（防抖动）
	if a+b != 200 {
		t.Errorf("选择次数: %d+%d", a, b)
	}
}

func TestConcurrentSafeCounter(t *testing.T) {
	if got := ConcurrentSafeCounter(1000); got != 1000 {
		t.Errorf("并发计数: got %d want 1000", got)
	}
}
