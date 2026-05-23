// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @title Flow Memory Task Escrow
/// @notice Minimal stand-alone escrow for testnet task settlement. Uses a pull-payment
/// pattern and a small reentrancy guard so agents withdraw after requester settlement.
contract TaskEscrow {
    enum Status { Open, Assigned, Settled, Disputed, Cancelled }

    struct Task {
        address requester;
        address agent;
        uint256 reward;
        Status status;
        bytes32 specHash;
        bytes32 resultHash;
    }

    uint256 public nextTaskId = 1;
    mapping(uint256 => Task) public tasks;
    mapping(address => uint256) public withdrawable;
    bool private locked;

    event TaskCreated(uint256 indexed taskId, address indexed requester, uint256 reward, bytes32 specHash);
    event TaskAssigned(uint256 indexed taskId, address indexed agent);
    event TaskSettled(uint256 indexed taskId, address indexed agent, bytes32 resultHash, uint256 reward);
    event TaskDisputed(uint256 indexed taskId, bytes32 evidenceHash);
    event TaskCancelled(uint256 indexed taskId);
    event Withdrawal(address indexed account, uint256 amount);

    modifier nonReentrant() {
        require(!locked, "reentrancy");
        locked = true;
        _;
        locked = false;
    }

    function createTask(bytes32 specHash) external payable returns (uint256 taskId) {
        require(msg.value > 0, "reward required");
        taskId = nextTaskId++;
        tasks[taskId] = Task({
            requester: msg.sender,
            agent: address(0),
            reward: msg.value,
            status: Status.Open,
            specHash: specHash,
            resultHash: bytes32(0)
        });
        emit TaskCreated(taskId, msg.sender, msg.value, specHash);
    }

    function assign(uint256 taskId, address agent) external {
        require(agent != address(0), "bad agent");
        Task storage task = tasks[taskId];
        require(msg.sender == task.requester, "not requester");
        require(task.status == Status.Open, "not open");
        task.agent = agent;
        task.status = Status.Assigned;
        emit TaskAssigned(taskId, agent);
    }

    function settle(uint256 taskId, bytes32 resultHash) external {
        Task storage task = tasks[taskId];
        require(msg.sender == task.requester, "not requester");
        require(task.status == Status.Assigned, "not assigned");
        task.status = Status.Settled;
        task.resultHash = resultHash;
        withdrawable[task.agent] += task.reward;
        emit TaskSettled(taskId, task.agent, resultHash, task.reward);
    }

    function dispute(uint256 taskId, bytes32 evidenceHash) external {
        Task storage task = tasks[taskId];
        require(msg.sender == task.requester || msg.sender == task.agent, "not participant");
        require(task.status == Status.Assigned, "not assigned");
        task.status = Status.Disputed;
        emit TaskDisputed(taskId, evidenceHash);
    }

    function cancel(uint256 taskId) external {
        Task storage task = tasks[taskId];
        require(msg.sender == task.requester, "not requester");
        require(task.status == Status.Open, "not open");
        task.status = Status.Cancelled;
        withdrawable[task.requester] += task.reward;
        emit TaskCancelled(taskId);
    }

    function withdraw() external nonReentrant {
        uint256 amount = withdrawable[msg.sender];
        require(amount > 0, "nothing to withdraw");
        withdrawable[msg.sender] = 0;
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "withdraw failed");
        emit Withdrawal(msg.sender, amount);
    }
}
