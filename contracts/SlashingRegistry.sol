// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @title SlashingRegistry
/// @notice Local unaudited record of reputation slash events. Does not move tokens or funds.
contract SlashingRegistry {
    struct Slash {
        address authority;
        address agent;
        uint256 amount;
        bytes32 reasonHash;
        uint64 recordedAt;
    }

    address public immutable authority;
    uint256 public nextSlashId = 1;
    mapping(uint256 => Slash) public slashes;
    mapping(address => uint256) public totalSlashed;

    event SlashRecorded(
        uint256 indexed slashId,
        address indexed authority,
        address indexed agent,
        uint256 amount,
        bytes32 reasonHash
    );

    constructor(address authority_) {
        require(authority_ != address(0), "invalid authority");
        authority = authority_;
    }

    function recordSlash(address agent, uint256 amount, bytes32 reasonHash) external returns (uint256 slashId) {
        require(msg.sender == authority, "not authority");
        require(agent != address(0), "invalid agent");
        require(amount != 0, "invalid amount");
        require(reasonHash != bytes32(0), "invalid reason");

        slashId = nextSlashId++;
        slashes[slashId] = Slash({
            authority: msg.sender,
            agent: agent,
            amount: amount,
            reasonHash: reasonHash,
            recordedAt: uint64(block.timestamp)
        });
        totalSlashed[agent] += amount;

        emit SlashRecorded(slashId, msg.sender, agent, amount, reasonHash);
    }
}
