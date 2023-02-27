function chat(msg, target)
	local pls = game:GetService 'Players'
	local rs = game:GetService 'ReplicatedStorage'
	local dcse = rs:WaitForChild 'DefaultChatSystemChatEvents'
	local smr = dcse:WaitForChild 'SayMessageRequest'
	smr:FireServer(msg, target or 'All')
	pls:Chat(msg)
end
