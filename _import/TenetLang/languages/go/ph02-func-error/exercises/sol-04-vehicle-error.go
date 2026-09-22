// exercises/sol-04-vehicle-error.go —— 练习 4 参考实现：自定义业务错误
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run sol-04-vehicle-error.go
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import (
	"errors"
	"fmt"
)

// VehicleError 是自定义业务错误类型，携带错误码与车辆 VIN。
type VehicleError struct {
	Code    int
	Vin     string
	Message string
}

func (e *VehicleError) Error() string {
	return fmt.Sprintf("vehicle error (code=%d, vin=%s): %s", e.Code, e.Vin, e.Message)
}

// checkVehicle 校验车辆状态：VIN 必填，电量过低不可上路。
func checkVehicle(vin string, soc float64) error {
	if vin == "" {
		return &VehicleError{Code: 1001, Vin: vin, Message: "vin is required"}
	}
	if soc < 20 {
		return &VehicleError{Code: 2001, Vin: vin, Message: fmt.Sprintf("soc %.0f%% below 20%%", soc)}
	}
	return nil
}

func main() {
	if err := checkVehicle("", 80); err != nil {
		var ve *VehicleError
		if errors.As(err, &ve) {
			fmt.Println("参数错误:", ve)
		}
	}

	if err := checkVehicle("LFV3A28K1A5000001", 15); err != nil {
		var ve *VehicleError
		if errors.As(err, &ve) {
			switch ve.Code {
			case 2001:
				fmt.Printf("车辆 %s 电量过低（code=%d），请充电\n", ve.Vin, ve.Code)
			default:
				fmt.Println("车辆校验失败:", ve)
			}
		}
	}

	if err := checkVehicle("LFV3A28K1A5000001", 80); err == nil {
		fmt.Println("车辆状态正常，可以上路")
	}
}
