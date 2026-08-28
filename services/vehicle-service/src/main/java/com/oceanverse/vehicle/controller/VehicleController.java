package com.oceanverse.vehicle.controller;

import com.oceanverse.vehicle.entity.Vehicle;
import com.oceanverse.vehicle.service.VehicleService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/vehicles")
public class VehicleController {

    private final VehicleService vehicleService;

    public VehicleController(VehicleService vehicleService) {
        this.vehicleService = vehicleService;
    }

    @GetMapping
    public List<Vehicle> list() {
        return vehicleService.findAll();
    }

    @GetMapping("/{vehicleId}")
    public ResponseEntity<Vehicle> get(@PathVariable String vehicleId) {
        return vehicleService.findByVehicleId(vehicleId)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping
    public Vehicle create(@RequestBody Vehicle vehicle) {
        return vehicleService.save(vehicle);
    }

    @PutMapping("/{vehicleId}")
    public ResponseEntity<Vehicle> update(@PathVariable String vehicleId, @RequestBody Vehicle vehicle) {
        return vehicleService.findByVehicleId(vehicleId)
                .map(existing -> {
                    vehicle.setId(existing.getId());
                    return ResponseEntity.ok(vehicleService.save(vehicle));
                })
                .orElse(ResponseEntity.notFound().build());
    }

    @DeleteMapping("/{vehicleId}")
    public ResponseEntity<Void> delete(@PathVariable String vehicleId) {
        return vehicleService.findByVehicleId(vehicleId)
                .map(v -> {
                    vehicleService.deleteById(v.getId());
                    return ResponseEntity.ok().<Void>build();
                })
                .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/health")
    public ResponseEntity<String> health() {
        return ResponseEntity.ok("OK");
    }
}
