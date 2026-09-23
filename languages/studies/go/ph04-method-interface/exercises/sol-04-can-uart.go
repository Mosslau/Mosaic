// 来源：exercises/README.md 练习 4 —— 用接口模拟 BUS/UART 数据读取参考实现
// 一句话说明：Reader 小接口 + BUS/UART 两个链路实现，采集器循环读取并用 errors.Is 处理链路中断。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：go run sol-04-can-uart.go
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"errors"
	"fmt"
)

// Frame 一条模拟数据帧
type Frame struct {
	Source string  // 来源：CAN0 / UART1
	Value  float64 // 采集值
}

// Reader 消费侧定义的小接口：一次读取一帧数据
type Reader interface {
	Read() (Frame, error)
}

// ErrLinkDown 哨兵错误：模拟链路中断
var ErrLinkDown = errors.New("link down")

// BUSReader 模拟 BUS 总线读取，读到 maxFrames 帧后持续返回链路故障
type BUSReader struct {
	frame     int
	maxFrames int
}

func (r *BUSReader) Read() (Frame, error) {
	r.frame++
	if r.frame > r.maxFrames {
		return Frame{}, ErrLinkDown
	}
	return Frame{Source: "CAN0", Value: float64(r.frame) * 1.5}, nil
}

// UARTReader 模拟 UART 串口读取
type UARTReader struct {
	frame     int
	maxFrames int
}

func (r *UARTReader) Read() (Frame, error) {
	r.frame++
	if r.frame > r.maxFrames {
		return Frame{}, ErrLinkDown
	}
	return Frame{Source: "UART1", Value: 100 + float64(r.frame)}, nil
}

// collect 对 Reader 接口编程：循环读取直到出错，返回帧数与总和
// 用 errors.Is 判断中断类型后正常结束——错误是值，不是异常，不 panic
func collect(r Reader) (count int, sum float64, err error) {
	for {
		f, err := r.Read()
		if err != nil {
			return count, sum, err
		}
		count++
		sum += f.Value
	}
}

func main() {
	readers := []Reader{
		&BUSReader{maxFrames: 4},
		&UARTReader{maxFrames: 3},
	}
	for _, r := range readers {
		count, sum, err := collect(r)
		if errors.Is(err, ErrLinkDown) {
			fmt.Printf("%T: 读到 %d 帧, 平均 %.2f, 链路中断（正常结束，不 panic）\n",
				r, count, sum/float64(count))
		} else {
			fmt.Printf("%T: 异常错误: %v\n", r, err)
		}
	}
}
