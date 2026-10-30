package com.ninebot.dataagent.api;

import com.ninebot.dataagent.domain.ApiModels.SandboxArtifactRequest;
import com.ninebot.dataagent.domain.ApiModels.SandboxCommandRequest;
import com.ninebot.dataagent.domain.ApiModels.SandboxCommandResponse;
import com.ninebot.dataagent.domain.ApiModels.SandboxCreateRequest;
import com.ninebot.dataagent.domain.ApiModels.SandboxFileInfo;
import com.ninebot.dataagent.domain.ApiModels.SandboxInfo;
import com.ninebot.dataagent.domain.ApiModels.SandboxReadFileRequest;
import com.ninebot.dataagent.domain.ApiModels.SandboxReadFileResponse;
import com.ninebot.dataagent.domain.ApiModels.SandboxWriteFileRequest;
import com.ninebot.dataagent.service.SandboxGatewayService;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

/** Java Sandbox Gateway v1 HTTP 契约。 */
@RestController
@RequestMapping("/internal/sandboxes")
public class SandboxGatewayController {
    private final SandboxGatewayService sandboxes;

    public SandboxGatewayController(SandboxGatewayService sandboxes) { this.sandboxes = sandboxes; }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public SandboxInfo create(@RequestBody SandboxCreateRequest request, @RequestHeader(value = "Idempotency-Key", required = false) String ignored) {
        return sandboxes.create(request);
    }

    @PutMapping("/{id}/files")
    public SandboxFileInfo write(@PathVariable String id, @RequestBody SandboxWriteFileRequest request) {
        return sandboxes.write(id, request.path(), request.contentBase64());
    }

    @PostMapping("/{id}/files:read")
    public SandboxReadFileResponse read(@PathVariable String id, @RequestBody SandboxReadFileRequest request) {
        return sandboxes.read(id, request.path());
    }

    @PostMapping("/{id}/commands")
    public SandboxCommandResponse run(@PathVariable String id, @RequestBody SandboxCommandRequest request) {
        return sandboxes.run(id, request);
    }

    @PostMapping("/{id}/artifacts")
    @ResponseStatus(HttpStatus.NOT_IMPLEMENTED)
    public void artifact(@PathVariable String id, @RequestBody SandboxArtifactRequest request) {
        throw new UnsupportedOperationException("object storage artifact backend is not configured");
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable String id) { sandboxes.delete(id); }
}
