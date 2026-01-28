package com.aswa.common.auth.session;

/**
 * Device information for session tracking.
 */
public record DeviceInfo(
    String userAgent,
    String ipAddress,
    String deviceType,
    String browser,
    String os,
    String country,
    String city
) {

    public static DeviceInfo fromRequest(String userAgent, String ipAddress) {
        // Parse user agent (use library like ua-parser in production)
        String deviceType = detectDeviceType(userAgent);
        String browser = detectBrowser(userAgent);
        String os = detectOS(userAgent);

        return new DeviceInfo(
            userAgent,
            ipAddress,
            deviceType,
            browser,
            os,
            null, // Geo lookup needed
            null
        );
    }

    private static String detectDeviceType(String userAgent) {
        if (userAgent == null) return "unknown";
        String ua = userAgent.toLowerCase();
        if (ua.contains("mobile") || ua.contains("android") || ua.contains("iphone")) {
            return "mobile";
        } else if (ua.contains("tablet") || ua.contains("ipad")) {
            return "tablet";
        }
        return "desktop";
    }

    private static String detectBrowser(String userAgent) {
        if (userAgent == null) return "unknown";
        String ua = userAgent.toLowerCase();
        if (ua.contains("chrome") && !ua.contains("edg")) return "Chrome";
        if (ua.contains("firefox")) return "Firefox";
        if (ua.contains("safari") && !ua.contains("chrome")) return "Safari";
        if (ua.contains("edg")) return "Edge";
        return "Other";
    }

    private static String detectOS(String userAgent) {
        if (userAgent == null) return "unknown";
        String ua = userAgent.toLowerCase();
        if (ua.contains("windows")) return "Windows";
        if (ua.contains("mac os")) return "macOS";
        if (ua.contains("linux")) return "Linux";
        if (ua.contains("android")) return "Android";
        if (ua.contains("iphone") || ua.contains("ipad")) return "iOS";
        return "Other";
    }

    public String getDisplayName() {
        return String.format("%s on %s (%s)", browser, os, deviceType);
    }
}
