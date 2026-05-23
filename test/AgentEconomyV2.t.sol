// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import "../contracts/AttestationRegistry.sol";
import "../contracts/DelegationRegistry.sol";
import "../contracts/DisputeResolver.sol";
import "../contracts/SlashingRegistry.sol";
import "../contracts/AgentTreasury.sol";
import "../contracts/CapabilityRegistry.sol";

contract EconomyV2Actor {
    function resolveDispute(DisputeResolver resolver, uint256 disputeId, bytes32 outcomeHash) external {
        resolver.resolveDispute(disputeId, outcomeHash);
    }

    function recordSlash(SlashingRegistry registry, address agent, uint256 amount, bytes32 reasonHash) external {
        registry.recordSlash(agent, amount, reasonHash);
    }
}

contract AgentEconomyV2Test {
    function testAttestationCreate() external {
        AttestationRegistry registry = new AttestationRegistry();
        address subject = address(0xA11CE);
        bytes32 schemaHash = keccak256("agent-performance-schema");
        bytes32 evidenceHash = keccak256("local-evidence");

        uint256 attestationId = registry.createAttestation(subject, schemaHash, evidenceHash);

        (
            address issuer,
            address recordedSubject,
            bytes32 recordedSchemaHash,
            bytes32 recordedEvidenceHash,
            ,
            bool revoked
        ) = registry.attestations(attestationId);
        assert(attestationId == 1);
        assert(issuer == address(this));
        assert(recordedSubject == subject);
        assert(recordedSchemaHash == schemaHash);
        assert(recordedEvidenceHash == evidenceHash);
        assert(!revoked);
    }

    function testDelegationCreateAndComplete() external {
        DelegationRegistry registry = new DelegationRegistry();
        address delegate = address(0xB0B);
        bytes32 termsHash = keccak256("delegation-terms");
        bytes32 completionHash = keccak256("delegation-result");

        uint256 delegationId = registry.createDelegation(delegate, termsHash);
        registry.completeDelegation(delegationId, completionHash);

        (
            address delegator,
            address recordedDelegate,
            bytes32 recordedTermsHash,
            bytes32 recordedCompletionHash,
            DelegationRegistry.Status status
        ) = registry.delegations(delegationId);
        assert(delegationId == 1);
        assert(delegator == address(this));
        assert(recordedDelegate == delegate);
        assert(recordedTermsHash == termsHash);
        assert(recordedCompletionHash == completionHash);
        assert(uint256(status) == uint256(DelegationRegistry.Status.Completed));
    }

    function testDisputeOpenAndResolveUnauthorizedRejection() external {
        DisputeResolver resolver = new DisputeResolver(address(this));
        EconomyV2Actor actor = new EconomyV2Actor();
        address respondent = address(0xCAFE);
        bytes32 evidenceHash = keccak256("dispute-evidence");
        bytes32 outcomeHash = keccak256("resolver-outcome");

        uint256 disputeId = resolver.openDispute(respondent, 7, evidenceHash);

        try actor.resolveDispute(resolver, disputeId, outcomeHash) {
            assert(false);
        } catch Error(string memory reason) {
            assert(keccak256(bytes(reason)) == keccak256(bytes("not resolver")));
        }

        resolver.resolveDispute(disputeId, outcomeHash);

        (
            address opener,
            address recordedRespondent,
            uint256 targetId,
            bytes32 recordedEvidenceHash,
            bytes32 recordedOutcomeHash,
            DisputeResolver.Status status
        ) = resolver.disputes(disputeId);
        assert(opener == address(this));
        assert(recordedRespondent == respondent);
        assert(targetId == 7);
        assert(recordedEvidenceHash == evidenceHash);
        assert(recordedOutcomeHash == outcomeHash);
        assert(uint256(status) == uint256(DisputeResolver.Status.Resolved));
    }

    function testSlashingRecordUnauthorizedRejection() external {
        SlashingRegistry registry = new SlashingRegistry(address(this));
        EconomyV2Actor actor = new EconomyV2Actor();
        address agent = address(0xDAD);
        bytes32 reasonHash = keccak256("failed-task");

        try actor.recordSlash(registry, agent, 3, reasonHash) {
            assert(false);
        } catch Error(string memory reason) {
            assert(keccak256(bytes(reason)) == keccak256(bytes("not authority")));
        }

        uint256 slashId = registry.recordSlash(agent, 3, reasonHash);

        (address authority, address recordedAgent, uint256 amount, bytes32 recordedReasonHash, ) = registry.slashes(slashId);
        assert(slashId == 1);
        assert(authority == address(this));
        assert(recordedAgent == agent);
        assert(amount == 3);
        assert(recordedReasonHash == reasonHash);
        assert(registry.totalSlashed(agent) == 3);
    }

    function testDisputeDoubleResolutionRejection() external {
        DisputeResolver resolver = new DisputeResolver(address(this));
        uint256 disputeId = resolver.openDispute(address(0xCAFE), 9, keccak256("dispute-evidence"));

        resolver.resolveDispute(disputeId, keccak256("first-outcome"));

        try resolver.resolveDispute(disputeId, keccak256("second-outcome")) {
            assert(false);
        } catch Error(string memory reason) {
            assert(keccak256(bytes(reason)) == keccak256(bytes("already resolved")));
        }
    }

    function testCapabilityRegistrySetAndGet() external {
        CapabilityRegistry registry = new CapabilityRegistry();
        bytes32 agentId = keccak256("agent");
        bytes32 capabilityId = keccak256("research");
        bytes32 capabilityHash = keccak256("manifest");

        registry.setCapability(agentId, capabilityId, capabilityHash, "ipfs://capability", true);
        CapabilityRegistry.CapabilityRecord memory record = registry.getCapability(agentId, capabilityId);

        assert(record.capabilityHash == capabilityHash);
        assert(keccak256(bytes(record.uri)) == keccak256(bytes("ipfs://capability")));
        assert(record.active);
    }

    function testAgentTreasuryCreditsBeneficiary() external {
        AgentTreasury treasury = new AgentTreasury(address(this));
        address beneficiary = address(0xBEEF);

        treasury.controllerCredit(beneficiary, 7);

        assert(treasury.withdrawable(beneficiary) == 7);
    }
}
