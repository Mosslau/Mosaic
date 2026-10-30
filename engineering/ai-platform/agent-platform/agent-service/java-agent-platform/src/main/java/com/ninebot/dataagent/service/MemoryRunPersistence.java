package com.ninebot.dataagent.service;

import com.ninebot.dataagent.domain.ApiModels.RunView;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Repository;

/** 默认开发实现：进程内保存 AgentRun 状态。 */
@Repository
@ConditionalOnProperty(prefix = "agent.persistence", name = "mode", havingValue = "memory", matchIfMissing = true)
public class MemoryRunPersistence implements RunPersistence {
    private final Map<String, RunView> runs = new ConcurrentHashMap<>();
    public void save(RunView run) { runs.put(run.runId(), run); }
    public RunView get(String runId) { return runs.get(runId); }
    public boolean contains(String runId) { return runs.containsKey(runId); }
}
