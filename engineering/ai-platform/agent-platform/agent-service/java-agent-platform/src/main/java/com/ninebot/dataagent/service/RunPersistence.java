package com.ninebot.dataagent.service;

import com.ninebot.dataagent.domain.ApiModels.RunView;

/** AgentRun 状态存储端口。 */
public interface RunPersistence {
    void save(RunView run);
    RunView get(String runId);
    boolean contains(String runId);
}
