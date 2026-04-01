// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title SecureVoting
/// @notice A coursework-friendly voting contract with whitelist-based voting.
/// @dev Stores only minimal on-chain data (addresses and vote counts).
contract SecureVoting {
    error NotOwner();
    error InvalidTimeRange();
    error InvalidCandidateList();
    error InvalidCandidateId();
    error EmptyCandidateName();
    error ZeroAddress();
    error AlreadyRegistered();
    error NotRegistered();
    error AlreadyVoted();
    error ElectionNotStarted();
    error ElectionEnded();
    error ElectionNotEnded();
    error TooManyVotersInBatch();

    struct Candidate {
        string name;
        uint256 voteCount;
    }

    address public immutable owner;
    string public electionTitle;
    uint64 public immutable startTime;
    uint64 public immutable endTime;
    uint256 public totalVotes;
    uint256 public totalRegisteredVoters;

    mapping(address => bool) public isRegisteredVoter;
    mapping(address => bool) public hasVoted;
    mapping(uint256 => Candidate) private candidates;
    uint256 private candidateTotal;

    uint256 public constant MAX_CANDIDATES = 20;
    uint256 public constant MAX_BATCH_REGISTRATION = 200;

    event CandidateCreated(uint256 indexed candidateId, string name);
    event VoterRegistered(address indexed voter);
    event VoteCast(address indexed voter, uint256 indexed candidateId);

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    modifier duringElection() {
        if (block.timestamp < startTime) revert ElectionNotStarted();
        if (block.timestamp > endTime) revert ElectionEnded();
        _;
    }

    modifier afterElection() {
        if (block.timestamp <= endTime) revert ElectionNotEnded();
        _;
    }

    constructor(
        string memory _title,
        string[] memory candidateNames,
        uint64 _startTime,
        uint64 _endTime,
        address[] memory initialVoters
    ) {
        if (_startTime >= _endTime) revert InvalidTimeRange();
        if (candidateNames.length < 2 || candidateNames.length > MAX_CANDIDATES) revert InvalidCandidateList();

        owner = msg.sender;
        electionTitle = _title;
        startTime = _startTime;
        endTime = _endTime;

        for (uint256 i = 0; i < candidateNames.length; i++) {
            if (bytes(candidateNames[i]).length == 0) revert EmptyCandidateName();
            candidates[i] = Candidate({name: candidateNames[i], voteCount: 0});
            emit CandidateCreated(i, candidateNames[i]);
        }
        candidateTotal = candidateNames.length;

        if (initialVoters.length > MAX_BATCH_REGISTRATION) revert TooManyVotersInBatch();
        for (uint256 i = 0; i < initialVoters.length; i++) {
            _registerVoter(initialVoters[i]);
        }
    }

    function registerVoter(address voter) external onlyOwner {
        _registerVoter(voter);
    }

    function batchRegisterVoters(address[] calldata voters) external onlyOwner {
        if (voters.length > MAX_BATCH_REGISTRATION) revert TooManyVotersInBatch();
        for (uint256 i = 0; i < voters.length; i++) {
            _registerVoter(voters[i]);
        }
    }

    function vote(uint256 candidateId) external duringElection {
        if (!isRegisteredVoter[msg.sender]) revert NotRegistered();
        if (hasVoted[msg.sender]) revert AlreadyVoted();
        if (candidateId >= candidateTotal) revert InvalidCandidateId();

        hasVoted[msg.sender] = true;
        totalVotes += 1;
        candidates[candidateId].voteCount += 1;

        emit VoteCast(msg.sender, candidateId);
    }

    function candidateCount() external view returns (uint256) {
        return candidateTotal;
    }

    function getCandidate(uint256 candidateId) external view returns (string memory name, uint256 voteCount) {
        if (candidateId >= candidateTotal) revert InvalidCandidateId();
        Candidate storage c = candidates[candidateId];
        return (c.name, c.voteCount);
    }

    function getElectionStatus() external view returns (string memory) {
        if (block.timestamp < startTime) return "PENDING";
        if (block.timestamp <= endTime) return "ACTIVE";
        return "ENDED";
    }

    function getAllResults() external view afterElection returns (string[] memory names, uint256[] memory votes) {
        names = new string[](candidateTotal);
        votes = new uint256[](candidateTotal);

        for (uint256 i = 0; i < candidateTotal; i++) {
            Candidate storage c = candidates[i];
            names[i] = c.name;
            votes[i] = c.voteCount;
        }
    }

    function getWinner()
        external
        view
        afterElection
        returns (uint256 winnerId, string memory winnerName, uint256 winnerVotes, bool isTie)
    {
        uint256 highestVotes = 0;
        uint256 highestId = 0;
        bool tie = false;

        for (uint256 i = 0; i < candidateTotal; i++) {
            uint256 count = candidates[i].voteCount;
            if (count > highestVotes) {
                highestVotes = count;
                highestId = i;
                tie = false;
            } else if (count == highestVotes && i != highestId) {
                tie = true;
            }
        }

        Candidate storage c = candidates[highestId];
        return (highestId, c.name, highestVotes, tie);
    }

    function _registerVoter(address voter) internal {
        if (voter == address(0)) revert ZeroAddress();
        if (isRegisteredVoter[voter]) revert AlreadyRegistered();
        isRegisteredVoter[voter] = true;
        totalRegisteredVoters += 1;
        emit VoterRegistered(voter);
    }
}
