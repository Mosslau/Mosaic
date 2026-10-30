package com.ninebot.dataagent.service;

import com.ninebot.dataagent.domain.ApiModels.RunView;
import org.springframework.stereotype.Service;

/** AgentRun 状态门面；实际实现由 agent.persistence.mode 选择。 */
@Service
public class RunStore {
    private final RunPersistence persistence;
    public RunStore(RunPersistence persistence) { this.persistence = persistence; }
    public void save(RunView run) { persistence.save(run); }
    public RunView get(String runId) { return persistence.get(runId); }
    public boolean contains(String runId) { return persistence.contains(runId); }
}
