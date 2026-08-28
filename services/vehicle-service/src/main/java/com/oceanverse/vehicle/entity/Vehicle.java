package com.oceanverse.vehicle.entity;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "vehicles")
public class Vehicle {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "vehicle_id", unique = true, nullable = false)
    private String vehicleId;

    @Column(name = "vin")
    private String vin;

    @Column(name = "model")
    private String model;

    @Column(name = "manufacture_date")
    private LocalDateTime manufactureDate;

    @Column(name = "bind_user_id")
    private Long bindUserId;

    @Column(name = "status")
    @Enumerated(EnumType.STRING)
    private VehicleStatus status = VehicleStatus.ACTIVE;

    @Column(name = "created_at")
    private LocalDateTime createdAt = LocalDateTime.now();

    @Column(name = "updated_at")
    private LocalDateTime updatedAt = LocalDateTime.now();

    public enum VehicleStatus {
        ACTIVE, INACTIVE, MAINTENANCE, RETIRED
    }

    // Getters and Setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getVehicleId() { return vehicleId; }
    public void setVehicleId(String vehicleId) { this.vehicleId = vehicleId; }
    public String getVin() { return vin; }
    public void setVin(String vin) { this.vin = vin; }
    public String getModel() { return model; }
    public void setModel(String model) { this.model = model; }
    public LocalDateTime getManufactureDate() { return manufactureDate; }
    public void setManufactureDate(LocalDateTime manufactureDate) { this.manufactureDate = manufactureDate; }
    public Long getBindUserId() { return bindUserId; }
    public void setBindUserId(Long bindUserId) { this.bindUserId = bindUserId; }
    public VehicleStatus getStatus() { return status; }
    public void setStatus(VehicleStatus status) { this.status = status; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
}
