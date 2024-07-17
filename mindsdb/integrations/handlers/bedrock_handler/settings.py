from pydantic_settings import BaseSettings
from botocore.exceptions import ClientError
from typing import Text, List, Dict, Optional, Any, ClassVar
from pydantic import BaseModel, Field, model_validator, field_validator

from mindsdb.integrations.handlers.bedrock_handler.utilities import create_amazon_bedrock_client
from mindsdb.integrations.utilities.handlers.validation_utilities import ParameterValidationUtilities


class AmazonBedrockHandlerSettings(BaseSettings):
    """
    Settings for Amazon Bedrock handler.

    Attributes
    ----------
    DEFAULT_MODE : Text
        The default mode for the handler.

    SUPPORTED_MODES : List
        List of supported modes for the handler.

    DEFAULT_TEXT_MODEL_ID : Text
        The default model ID to use for text generation. This will be the default model ID for the default, conversational and conversational-full modes.
    """
    # Modes.
    # TODO: Add other modes.
    DEFAULT_MODE: ClassVar[Text] = 'default'
    SUPPORTED_MODES: ClassVar[List] = ['default']

    # Model IDs.
    DEFAULT_TEXT_MODEL_ID: ClassVar[Text] = 'amazon.titan-text-express-v1'


class AmazonBedrockHandlerEngineConfig(BaseModel):
    """
    Model for Amazon Bedrock engines.

    Attributes
    ----------
    aws_access_key_id : Text
        The AWS access key ID.

    aws_secret_access_key : Text
        The AWS secret access key.

    region_name : Text
        The AWS region name.

    aws_session_token : Text, Optional
        The AWS session token. Optional, but required for temporary security credentials.
    """
    aws_access_key_id: Text
    aws_secret_access_key: Text
    region_name: Text
    aws_session_token: Optional[Text]

    class Config:
        extra = "forbid"

    @model_validator(mode="before")
    @classmethod
    def check_if_params_contain_typos(cls, values: Any) -> Any:
        """
        Validator to check if there are any typos in the parameters.

        Args:
            values (Any): Engine configuration.

        Raises:
            ValueError: If there are any typos in the parameters.
        """
        ParameterValidationUtilities.validate_parameter_spelling(cls, values)

        return values

    @model_validator(mode="after")
    @classmethod
    def check_access_to_amazon_bedrock(cls, model: BaseModel) -> BaseModel:
        """
        Validator to check if the Amazon Bedrock credentials are valid and Amazon Bedrock is accessible.

        Args:
            model (BaseModel): Engine configuration.

        Raises:
            ValueError: If the AWS credentials are invalid or do not have access to Amazon Bedrock.
        """
        bedrock_client = create_amazon_bedrock_client(
            model.aws_access_key_id,
            model.aws_secret_access_key,
            model.region_name,
            model.aws_session_token
        )

        try:
            bedrock_client.list_foundation_models()
        except ClientError as e:
            raise ValueError(f"Invalid Amazon Bedrock credentials: {e}!")

        return model


class AmazonBedrockHandlerModelConfig(BaseModel):
    """
    Configuration model for Amazon Bedrock models.

    Attributes
    ----------
    model_id : Text
        The ID of the model in Amazon Bedrock.

    mode : Optional[Text]
        The mode to run the handler model in. The supported modes are defined in AmazonBedrockHandlerSettings.

    prompt_template : Optional[Text]
        The base template for prompts with placeholders.

    question_column : Optional[Text]
        The column name for questions to be asked.

    context_column : Optional[Text]
        The column name for context to be provided with the questions.

    temperature : Optional[float]
        The setting for the randomness in the responses generated by the model.

    top_p : Optional[float]
        The setting for the probability of the tokens in the responses generated by the model.

    max_tokens : Optional[int]
        The maximum number of tokens to generate in the responses.

    stop : Optional[List[Text]]
        The list of sequences to stop the generation of tokens in the responses.

    connection_args : Dict
        The connection arguments passed required to connect to Amazon Bedrock. These are AWS credentials provided when creating the engine.
    """
    # User-provided Handler Model Prameters: These are parameters specific to the MindsDB handler for Amazon Bedrock provided by the user.
    model_id: Text = Field(None)
    mode: Optional[Text] = Field(AmazonBedrockHandlerSettings.DEFAULT_MODE)
    prompt_template: Optional[Text] = Field(None)
    question_column: Optional[Text] = Field(None)
    context_column: Optional[Text] = Field(None)

    # Amazon Bedrock Model Parameters: These are parameters specific to the models in Amazon Bedrock. They are provided by the user.
    temperature: Optional[float] = Field(None, bedrock_model_param=True, bedrock_model_param_name='temperature')
    top_p: Optional[float] = Field(None, bedrock_model_param=True, bedrock_model_param_name='topP')
    max_tokens: Optional[int] = Field(None, bedrock_model_param=True, bedrock_model_param_name='maxTokens')
    stop: Optional[List[Text]] = Field(None, bedrock_model_param=True, bedrock_model_param_name='stopSequences')

    # System-provided Handler Model Parameters: These are parameters specific to the MindsDB handler for Amazon Bedrock provided by the system.
    connection_args: Dict = Field(None, exclude=True)

    class Config:
        extra = "forbid"

    @model_validator(mode="before")
    @classmethod
    def check_if_params_contain_typos(cls, values: Any) -> Any:
        """
        Validator to check if there are any typos in the parameters.

        Args:
            values (Any): Model configuration.

        Raises:
            ValueError: If there are any typos in the parameters.
        """
        ParameterValidationUtilities.validate_parameter_spelling(cls, values)

        return values
    
    @field_validator("mode")
    @classmethod
    def check_if_mode_is_supported(cls, mode: Text) -> Text:
        """
        Validator to check if the mode provided is supported.

        Args:
            mode (Text): The mode to run the handler model in.

        Raises:
            ValueError: If the mode provided is not supported.
        """
        if mode not in AmazonBedrockHandlerSettings.SUPPORTED_MODES:
            raise ValueError(f"Mode {mode} is not supported. The supported modes are {''.join(AmazonBedrockHandlerSettings.SUPPORTED_MODES)}!")

        return mode

    @model_validator(mode="after")
    @classmethod
    def check_if_model_id_is_valid_and_correct_for_mode(cls, model: BaseModel) -> BaseModel:
        """
        Validator to check if the model ID and the parameters provided for the model are valid.
        If a model ID is not provided, the default model ID for that mode will be used.

        Args:
            values (Any): Model configuration.

        Raises:
            ValueError: If the model ID provided is invalid or the parameters provided are invalid for the chosen model.
        """
        # TODO: Set the default model ID for other modes.
        if model.model_id is None:
            if model.mode == 'default':
                model.model_id = AmazonBedrockHandlerSettings.DEFAULT_TEXT_MODEL_ID

            # If the default model ID is used, skip the validation.
            return model

        bedrock_client = create_amazon_bedrock_client(
            **model.connection_args
        )

        try:
            # Check if the model ID is valid and accessible.
            model = bedrock_client.get_foundation_model(modelIdentifier=model.model_id)
        except ClientError as e:
            raise ValueError(f"Invalid Amazon Bedrock model ID: {e}!")
        
        # Check if the model is suitable for the mode provided.
        if model.mode == 'default':
            if 'TEXT' not in model['modelDetails']['outputModalities']:
                raise ValueError(f"The models used for the {model.mode} should support text generation!")

        return model

    @model_validator(mode="after")
    @classmethod
    def check_if_mode_params_are_valid(cls, model: BaseModel) -> BaseModel:
        """
        Validator to check if the parameters required for the chosen mode provided are valid.

        Args:
            model (BaseModel): Handler model configuration.

        Raises:
            ValueError: If the parameters provided are invalid for the mode provided.
        """
        # If the mode is default, one of the following need to be provided:
        # 1. prompt_template.
        # 2. question_column with an optional context_column.
        # TODO: Find the other possible parameters/combinations for the default mode.
        if model.mode == 'default':
            if model.prompt_template is None and model.question_column is None:
                raise ValueError("Either prompt_template or question_column with an optional context_column need to be provided for the default mode!")

            if model.prompt_template is not None and model.question_column is not None:
                raise ValueError("Only one of prompt_template or question_column with an optional context_column can be provided for the default mode!")
            
            if model.context is not None and model.question_column is None:
                raise ValueError("context_column can only be provided with question_column for the default mode!")

        # TODO: Add validations for other modes.

        return model

    def model_dump(self) -> Dict:
        """
        Dumps the model configuration to a dictionary.

        Returns:
            Dict: The model configuration.
        """
        bedrock_model_param_names = [val.get("bedrock_model_param_name") for key, val in self.model_json_schema(mode='serialization')['properties'].items() if val.get("bedrock_model_param")]
        bedrock_model_params = [key for key, val in self.model_json_schema(mode='serialization')['properties'].items() if val.get("bedrock_model_param")]

        handler_model_params = [key for key, val in self.model_json_schema(mode='serialization')['properties'].items() if not val.get("bedrock_model_param")]

        inference_config = {}
        for index, key in enumerate(bedrock_model_params):
            if getattr(self, key) is not None:
                inference_config[bedrock_model_param_names[index]] = getattr(self, key)

        return {
            "inference_config": inference_config,
            **{key: getattr(self, key) for key in handler_model_params}
        }
