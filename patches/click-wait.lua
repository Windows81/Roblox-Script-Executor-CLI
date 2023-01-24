local mouse = game.Players.LocalPlayer:GetMouse()
---@diagnostic disable-next-line: undefined-global
local _ = WAIT_D and task.wait(WAIT_D) or mouse.Button1Up:Wait()
