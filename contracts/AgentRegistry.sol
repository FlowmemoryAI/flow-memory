// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @title Flow Memory Agent Registry
/// @notice Registers agent DIDs, capability manifest hashes, and controller addresses.
contract AgentRegistry {
    struct AgentRecord {
        address controller;
        string did;
        bytes32 manifestHash;
        string manifestURI;
        uint64 registeredAt;
        uint64 updatedAt;
        bool active;
    }

    mapping(bytes32 => AgentRecord) private records;
    mapping(address => bytes32[]) private controllerAgents;

    event AgentRegistered(bytes32 indexed agentId, address indexed controller, string did, bytes32 manifestHash, string manifestURI);
    event AgentUpdated(bytes32 indexed agentId, bytes32 manifestHash, string manifestURI, bool active);
    event ControllerTransferred(bytes32 indexed agentId, address indexed oldController, address indexed newController);

    error EmptyDID();
    error EmptyManifestHash();
    error AlreadyRegistered();
    error NotRegistered();
    error NotController();
    error InvalidController();

    modifier onlyController(bytes32 agentId) {
        AgentRecord storage record = records[agentId];
        if (record.controller == address(0)) revert NotRegistered();
        if (record.controller != msg.sender) revert NotController();
        _;
    }

    function registerAgent(string calldata did, bytes32 manifestHash, string calldata manifestURI) external returns (bytes32 agentId) {
        if (bytes(did).length == 0) revert EmptyDID();
        if (manifestHash == bytes32(0)) revert EmptyManifestHash();
        agentId = computeAgentId(did);
        if (records[agentId].controller != address(0)) revert AlreadyRegistered();
        records[agentId] = AgentRecord({
            controller: msg.sender,
            did: did,
            manifestHash: manifestHash,
            manifestURI: manifestURI,
            registeredAt: uint64(block.timestamp),
            updatedAt: uint64(block.timestamp),
            active: true
        });
        controllerAgents[msg.sender].push(agentId);
        emit AgentRegistered(agentId, msg.sender, did, manifestHash, manifestURI);
    }

    function updateManifest(bytes32 agentId, bytes32 manifestHash, string calldata manifestURI, bool active) external onlyController(agentId) {
        if (manifestHash == bytes32(0)) revert EmptyManifestHash();
        AgentRecord storage record = records[agentId];
        record.manifestHash = manifestHash;
        record.manifestURI = manifestURI;
        record.active = active;
        record.updatedAt = uint64(block.timestamp);
        emit AgentUpdated(agentId, manifestHash, manifestURI, active);
    }

    function transferController(bytes32 agentId, address newController) external onlyController(agentId) {
        if (newController == address(0)) revert InvalidController();
        address oldController = records[agentId].controller;
        records[agentId].controller = newController;
        records[agentId].updatedAt = uint64(block.timestamp);
        controllerAgents[newController].push(agentId);
        emit ControllerTransferred(agentId, oldController, newController);
    }

    function getAgent(bytes32 agentId) external view returns (AgentRecord memory) {
        AgentRecord memory record = records[agentId];
        if (record.controller == address(0)) revert NotRegistered();
        return record;
    }

    function agentsForController(address controller) external view returns (bytes32[] memory) {
        return controllerAgents[controller];
    }

    function computeAgentId(string memory did) public pure returns (bytes32) {
        return keccak256(abi.encodePacked(did));
    }
}
