/*
 *  Copyright (c) 2026 Metaform Systems, Inc.
 *
 *  This program and the accompanying materials are made available under the
 *  terms of the Apache License, Version 2.0 which is available at
 *  https://www.apache.org/licenses/LICENSE-2.0
 *
 *  SPDX-License-Identifier: Apache-2.0
 *
 *  Contributors:
 *       Metaform Systems, Inc. - initial API and implementation
 *
 */

package org.eclipse.edc.mvd.controlplane.identityclaim;

import org.eclipse.edc.policy.cel.function.context.CelClaim;
import org.eclipse.edc.policy.cel.function.context.CelParticipantAgentClaimMapperRegistry;
import org.eclipse.edc.runtime.metamodel.annotation.Extension;
import org.eclipse.edc.runtime.metamodel.annotation.Inject;
import org.eclipse.edc.spi.system.ServiceExtension;
import org.eclipse.edc.spi.system.ServiceExtensionContext;

/**
 * Exposes the verified counterparty identity (its participant DID) to CEL policy
 * expressions as {@code ctx.agent.claims.identity}. The stock DCP claim mapper only
 * publishes the presented verifiable credentials ({@code ctx.agent.claims.vc}); the
 * raw identity is not otherwise reachable from a policy. With this claim available,
 * policies can be scoped to a single participant DID, e.g.
 * <pre>ctx.agent.claims.identity == this.rightOperand</pre>
 * which the AM2Scale dataspace uses for directed quality-data feedback (a report
 * that only the original data provider may retrieve).
 */
@Extension(value = IdentityClaimMapperExtension.NAME)
public class IdentityClaimMapperExtension implements ServiceExtension {

    public static final String NAME = "AM2Scale Identity Claim Mapper";
    public static final String IDENTITY_CLAIM = "identity";

    @Inject
    private CelParticipantAgentClaimMapperRegistry claimMapperRegistry;

    @Override
    public String name() {
        return NAME;
    }

    @Override
    public void initialize(ServiceExtensionContext context) {
        claimMapperRegistry.registerClaimMapper(
                agent -> new CelClaim(IDENTITY_CLAIM, agent.getIdentity()));
        context.getMonitor().info("Identity claim mapper registered: reachable as ctx.agent.claims."
                + IDENTITY_CLAIM + " in policies");
    }
}
