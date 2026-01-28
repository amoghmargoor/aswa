package com.aswa.common.security.scanning;

import java.util.List;
import java.util.Optional;

/**
 * Interface for dependency inventory tracking.
 */
public interface DependencyInventory {

    /**
     * Get all dependencies.
     */
    List<SecurityScanService.Dependency> getAllDependencies();

    /**
     * Get dependency by name.
     */
    Optional<SecurityScanService.Dependency> getDependency(String name);

    /**
     * Refresh dependency list.
     */
    void refresh();
}
