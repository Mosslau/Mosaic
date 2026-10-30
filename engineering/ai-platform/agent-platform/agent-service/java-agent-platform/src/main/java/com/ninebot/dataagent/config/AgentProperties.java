package com.ninebot.dataagent.config;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

/** Java 控制平面与 Python Runtime、Gateway 的部署配置。 */
@ConfigurationProperties(prefix = "agent")
public class AgentProperties {
    private RuntimeProperties runtime = new RuntimeProperties();
    private GatewayProperties gateway = new GatewayProperties();

    public RuntimeProperties getRuntime() { return runtime; }
    public void setRuntime(RuntimeProperties runtime) { this.runtime = runtime; }
    public GatewayProperties getGateway() { return gateway; }
    public void setGateway(GatewayProperties gateway) { this.gateway = gateway; }

    public static class RuntimeProperties {
        private String baseUrl = "http://127.0.0.1:8800";
        private String accessKey;
        private String secretKey;
        /** Deprecated local migration fallback; production must use AK/SK. */
        private String internalToken;
        private Duration connectTimeout = Duration.ofSeconds(3);
        private Duration readTimeout = Duration.ofSeconds(30);
        public String getBaseUrl() { return baseUrl; }
        public void setBaseUrl(String baseUrl) { this.baseUrl = baseUrl; }
        public String getAccessKey() { return accessKey; }
        public void setAccessKey(String accessKey) { this.accessKey = accessKey; }
        public String getSecretKey() { return secretKey; }
        public void setSecretKey(String secretKey) { this.secretKey = secretKey; }
        public String getInternalToken() { return internalToken; }
        public void setInternalToken(String internalToken) { this.internalToken = internalToken; }
        public Duration getConnectTimeout() { return connectTimeout; }
        public void setConnectTimeout(Duration connectTimeout) { this.connectTimeout = connectTimeout; }
        public Duration getReadTimeout() { return readTimeout; }
        public void setReadTimeout(Duration readTimeout) { this.readTimeout = readTimeout; }
    }

    public static class GatewayProperties {
        private String accessKey;
        private String secretKey;
        private String internalToken;
        private SandboxProperties sandbox = new SandboxProperties();
        public String getAccessKey() { return accessKey; }
        public void setAccessKey(String accessKey) { this.accessKey = accessKey; }
        public String getSecretKey() { return secretKey; }
        public void setSecretKey(String secretKey) { this.secretKey = secretKey; }
        public String getInternalToken() { return internalToken; }
        public void setInternalToken(String internalToken) { this.internalToken = internalToken; }
        public SandboxProperties getSandbox() { return sandbox; }
        public void setSandbox(SandboxProperties sandbox) { this.sandbox = sandbox; }
    }

    public static class SandboxProperties {
        private String accessKey;
        private String secretKey;
        private boolean enabled;
        public String getAccessKey() { return accessKey; }
        public void setAccessKey(String accessKey) { this.accessKey = accessKey; }
        public String getSecretKey() { return secretKey; }
        public void setSecretKey(String secretKey) { this.secretKey = secretKey; }
        private boolean commandExecutionEnabled;
        public boolean isEnabled() { return enabled; }
        public void setEnabled(boolean enabled) { this.enabled = enabled; }
        public boolean isCommandExecutionEnabled() { return commandExecutionEnabled; }
        public void setCommandExecutionEnabled(boolean commandExecutionEnabled) { this.commandExecutionEnabled = commandExecutionEnabled; }
    }
}
