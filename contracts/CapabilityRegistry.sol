// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @title Flow Memory Capability Registry
/// @notice Minimal capability manifest registry for unaudited local/testnet agent experiments.
contract CapabilityRegistry {
    struct CapabilityRecord {
        bytes32 capabilityHash;
        string uri;
        uint64 updatedAt;
        bool active;
    }

    mapping(bytes32 => mapping(bytes32 => CapabilityRecord)) private records;

    event CapabilitySet(bytes32 indexed agentId, bytes32 indexed capabilityId, bytes32 capabilityHash, string uri, bool active);

    error EmptyHash();

    function setCapability(bytes32 agentId, bytes32 capabilityId, bytes32 capabilityHash, string calldata uri, bool active) external {
        if (capabilityHash == bytes32(0)) revert EmptyHash();
        records[agentId][capabilityId] = CapabilityRecord({
            capabilityHash: capabilityHash,
            uri: uri,
            updatedAt: uint64(block.timestamp),
            active: active
        });
        emit CapabilitySet(agentId, capabilityId, capabilityHash, uri, active);
    }

    function getCapability(bytes32 agentId, bytes32 capabilityId) external view returns (CapabilityRecord memory) {
        return records[agentId][capabilityId];
    }
}
