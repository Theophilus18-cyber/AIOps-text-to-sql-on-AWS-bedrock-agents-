variable "name" {
  description = "Guardrail name"
  type        = string
}

variable "description" {
  description = "Guardrail description"
  type        = string
  default     = "Text-to-SQL guardrail"
}

variable "blocked_input_messaging" {
  description = "Message returned when input is blocked"
  type        = string
  default     = "I'm sorry, I can't help with that request."
}

variable "blocked_outputs_messaging" {
  description = "Message returned when output is blocked"
  type        = string
  default     = "I'm sorry, the model's response was blocked by the guardrail."
}
