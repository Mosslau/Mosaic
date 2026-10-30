package com.ninebot.dataagent.api;

import com.ninebot.dataagent.domain.ApiModels.RunAccepted;
import com.ninebot.dataagent.domain.ApiModels.RunRequest;
import com.ninebot.dataagent.domain.ApiModels.RunView;
import com.ninebot.dataagent.service.RedisEventSseService;
import com.ninebot.dataagent.service.RunService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

/** 对外 AgentRun API：提交、状态、取消和 SSE。 */
@RestController
@RequestMapping("/api/agent-runs")
public class RunController {
    private final RunService runs;
    private final RedisEventSseService events;

    public RunController(RunService runs, RedisEventSseService events) {
        this.runs = runs;
        this.events = events;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.ACCEPTED)
    public RunAccepted submit(@Valid @RequestBody RunRequest request) { return runs.submit(request); }

    @GetMapping("/{runId}")
    public RunView get(@PathVariable String runId) { return runs.get(runId); }

    @PostMapping("/{runId}/cancel")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void cancel(@PathVariable String runId) { runs.cancel(runId); }

    @GetMapping(value = "/{runId}/events", produces = "text/event-stream")
    public SseEmitter events(@PathVariable String runId, @RequestParam(defaultValue = "0-0") String lastEventId) {
        return events.open(runId, lastEventId);
    }
}
