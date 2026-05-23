// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @title TaskMarketplace
/// @notice Minimal bid/ask registry. Escrowed settlement belongs in TaskEscrow.
contract TaskMarketplace {
    enum Status { Open, Assigned, Closed, Cancelled }

    struct Task {
        address requester;
        address assignee;
        uint256 maxReward;
        bytes32 specHash;
        Status status;
    }

    struct Bid {
        address bidder;
        uint256 price;
        bytes32 termsHash;
        bool active;
    }

    uint256 public nextTaskId = 1;
    mapping(uint256 => Task) public tasks;
    mapping(uint256 => Bid[]) public bids;

    event TaskPosted(uint256 indexed taskId, address indexed requester, uint256 maxReward, bytes32 specHash);
    event BidPosted(uint256 indexed taskId, uint256 indexed bidIndex, address indexed bidder, uint256 price, bytes32 termsHash);
    event TaskAssigned(uint256 indexed taskId, address indexed assignee, uint256 bidIndex);
    event TaskClosed(uint256 indexed taskId);

    function postTask(uint256 maxReward, bytes32 specHash) external returns (uint256 taskId) {
        taskId = nextTaskId++;
        tasks[taskId] = Task({
            requester: msg.sender,
            assignee: address(0),
            maxReward: maxReward,
            specHash: specHash,
            status: Status.Open
        });
        emit TaskPosted(taskId, msg.sender, maxReward, specHash);
    }

    function postBid(uint256 taskId, uint256 price, bytes32 termsHash) external returns (uint256 bidIndex) {
        Task storage task = tasks[taskId];
        require(task.status == Status.Open, "not open");
        require(price <= task.maxReward, "price too high");
        bids[taskId].push(Bid({bidder: msg.sender, price: price, termsHash: termsHash, active: true}));
        bidIndex = bids[taskId].length - 1;
        emit BidPosted(taskId, bidIndex, msg.sender, price, termsHash);
    }

    function assign(uint256 taskId, uint256 bidIndex) external {
        Task storage task = tasks[taskId];
        require(msg.sender == task.requester, "not requester");
        require(task.status == Status.Open, "not open");
        Bid storage bid = bids[taskId][bidIndex];
        require(bid.active, "inactive bid");
        task.assignee = bid.bidder;
        task.status = Status.Assigned;
        emit TaskAssigned(taskId, bid.bidder, bidIndex);
    }

    function close(uint256 taskId) external {
        Task storage task = tasks[taskId];
        require(msg.sender == task.requester, "not requester");
        require(task.status == Status.Assigned, "not assigned");
        task.status = Status.Closed;
        emit TaskClosed(taskId);
    }
}
