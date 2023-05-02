function chat(msg, target, skip_smr, skip_pls)
	if not skip_smr then
		local rs = game:GetService 'ReplicatedStorage'
		local dcse = rs:WaitForChild 'DefaultChatSystemChatEvents'
		local smr = dcse:WaitForChild 'SayMessageRequest'
		smr:FireServer(msg, target or 'All')
	end
	if not skip_pls then
		local pls = game:GetService 'Players'
		pls:Chat(msg)
	end
end
